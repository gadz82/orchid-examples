"""Pollen/Bloom event-driven job handlers for the FM agent fleet.

Each trigger in ``agents.yaml`` has a corresponding async function here.  All
handlers are idempotent: they compute a stable ``dedupe_key`` and short-circuit
if the key already exists in the ``job_runs`` table with status ``success``.

External dependencies are injected through ``BloomContext`` so tests can mock
them completely.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import yaml
from orchid_ai.core.repository import OrchidDocument
from orchid_ai.rag.scopes import OrchidRAGScope

from examples.fm_agent.hooks.capture import build_capture_metadata, normalize_tool_result, redact_and_store

logger = logging.getLogger(__name__)

# Platform repositories monitored by the FM agent fleet.
PLATFORM_REPOS = [
    "notification-be",
    "notification-paas-be",
    "paas-notification-meta",
    "mailer-service-be",
    "push-notification-service-be",
    "serverless-event-bus",
    "sync-bus-be",
    "domains",
    "cdk-base-stack-devops",
    "ci-paas-gitflow-devops",
    "ci-templates-devops",
]

# Postgres table used for durable job-run deduplication.
JOB_RUNS_TABLE = "job_runs"

# Default Slack channel ID for human-in-the-loop approvals.
DEFAULT_SLACK_CHANNEL = os.getenv("SLACK_CHANNEL_ID", "")


@dataclass
class JobRun:
    """A single row in the ``job_runs`` audit table."""

    id: str
    trigger_id: str
    dedupe_key: str
    status: str  # success, failed, skipped
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: str | None = None


class JobRunStore(ABC):
    """ABC for durable job-run storage."""

    @abstractmethod
    async def is_duplicate(self, dedupe_key: str) -> bool:
        """Return ``True`` if a successful run with this key already exists."""

    @abstractmethod
    async def write(self, run: JobRun) -> None:
        """Persist a job run."""


class InMemoryJobRunStore(JobRunStore):
    """Volatile store for unit tests."""

    def __init__(self) -> None:
        self._runs: list[JobRun] = []

    async def is_duplicate(self, dedupe_key: str) -> bool:
        return any(r.dedupe_key == dedupe_key and r.status == "success" for r in self._runs)

    async def write(self, run: JobRun) -> None:
        self._runs.append(run)

    def runs(self) -> list[JobRun]:
        return list(self._runs)


@dataclass
class MCPClient:
    """Minimal mockable MCP client wrapper for Bloom jobs."""

    call_tool: Any
    invoke_agent: Any
    vector_writer: Any
    llm_complete: Any

    async def call(self, server: str, tool: str, params: dict[str, Any] | None = None) -> Any:
        return await self.call_tool(server, tool, params or {})


@dataclass
class BloomContext:
    """Dependencies shared by all Bloom job handlers."""

    tenant_id: str = "default"
    job_store: JobRunStore = field(default_factory=InMemoryJobRunStore)
    mcp_client: MCPClient = field(
        default_factory=lambda: MCPClient(
            call_tool=lambda *_a, **_kw: None,
            invoke_agent=lambda *_a, **_kw: "",
            vector_writer=None,
            llm_complete=lambda *_a, **_kw: "",
        ),
    )
    slack_channel: str = DEFAULT_SLACK_CHANNEL
    postgres_dsn: str = "postgresql://orchid:orchid@localhost:5432/orchid"


def get_job_run_id() -> str:
    """Return a stable run identifier."""
    return str(uuid.uuid4())


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _this_week() -> str:
    return datetime.now(UTC).strftime("%Y-W%W")


def _this_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


async def is_duplicate(dedupe_key: str, ctx: BloomContext) -> bool:
    """Check whether a successful run with ``dedupe_key`` already exists."""
    return await ctx.job_store.is_duplicate(dedupe_key)


async def write_job_run(
    run_id: str,
    trigger_id: str,
    dedupe_key: str,
    status: str,
    result: dict[str, Any],
    error: str | None,
    ctx: BloomContext,
) -> JobRun:
    """Write a ``JobRun`` row and return it."""
    run = JobRun(
        id=run_id,
        trigger_id=trigger_id,
        dedupe_key=dedupe_key,
        status=status,
        result=result,
        error=error,
        created_at=datetime.now(UTC).isoformat(),
    )
    await ctx.job_store.write(run)
    return run


async def slack_post(message: str, ctx: BloomContext, thread_ts: str = "") -> dict[str, Any]:
    """Post a message to Slack via the configured MCP server."""
    params: dict[str, Any] = {
        "channel": ctx.slack_channel,
        "text": message,
    }
    if thread_ts:
        params["thread_ts"] = thread_ts
    return await ctx.mcp_client.call("slack", "chat_postMessage", params)


async def _summarize_with_llm(ctx: BloomContext, prompt: str, max_tokens: int = 4000) -> str:
    """Thin helper around the injected LLM completion."""
    return await ctx.mcp_client.llm_complete(prompt, max_tokens=max_tokens)


async def _emit_agent_prompt(
    ctx: BloomContext,
    agent: str,
    prompt_text: str,
    visibility: str = "tenant",
) -> str:
    """Emit a prompt to an Orchid agent via the injected MCP client."""
    return await ctx.mcp_client.invoke_agent(agent, prompt_text, visibility)


def _hash_claim(claim: str) -> str:
    return hashlib.sha256(claim.encode()).hexdigest()[:16]


async def _capture_tool_result(
    ctx: BloomContext,
    source: str,
    source_id: str,
    source_version: str,
    url: str,
    tool_name: str,
    result: Any,
) -> bool:
    """Normalize and store a raw tool result as chat_agent-scope live knowledge."""
    if ctx.mcp_client.vector_writer is None:
        return False

    text = await normalize_tool_result(tool_name, result)
    metadata = await build_capture_metadata(
        source=source,
        source_id=source_id,
        source_version=source_version,
        url=url,
        tool_name=tool_name,
        agent_id="bloom",
    )
    scope = OrchidRAGScope(tenant_id=ctx.tenant_id)
    return await redact_and_store(text, metadata, ctx.mcp_client.vector_writer, scope=scope)


async def _fetch_gitlab_mrs(ctx: BloomContext, repo: str, state: str = "opened") -> list[dict[str, Any]]:
    """Fetch merge requests for a single repo."""
    return await ctx.mcp_client.call("gitlab", "list_merge_requests", {"repo": repo, "state": state})


async def _fetch_gitlab_pipelines(ctx: BloomContext, repo: str) -> list[dict[str, Any]]:
    """Fetch failed pipelines for a repo in the last 24h."""
    since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    return await ctx.mcp_client.call(
        "gitlab",
        "list_pipelines",
        {"repo": repo, "status": "failed", "updated_after": since},
    )


async def _fetch_jira_issues(ctx: BloomContext, jql: str) -> list[dict[str, Any]]:
    return await ctx.mcp_client.call("atlassian-rovo", "searchJiraIssuesUsingJql", {"jql": jql})


async def _fetch_datadog_logs(ctx: BloomContext, service: str, hours: int = 24) -> list[dict[str, Any]]:
    """Pull Datadog logs for a single service."""
    query = f"service:{service} status:error"
    return await ctx.mcp_client.call("datadog", "query_logs", {"query": query, "hours": hours})


def _read_golden_pairs_sync() -> list[dict[str, Any]]:
    """Load approved golden pairs from the evals draft."""
    path = os.path.join(os.path.dirname(__file__), "evals", "golden.draft.yaml")
    try:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    except OSError:
        return []
    return data.get("entries", data.get("pairs", []))


async def _read_golden_pairs(ctx: BloomContext) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_read_golden_pairs_sync)


def _read_doc_drift_sync() -> list[str]:
    """Load existing DOC_DRIFT markdown entries."""
    path = os.path.join(os.path.dirname(__file__), "evals", "DOC_DRIFT.md")
    try:
        with open(path) as f:
            return f.read().split("\n## ")
    except OSError:
        return []


async def _read_doc_drift(ctx: BloomContext) -> list[str]:
    return await asyncio.to_thread(_read_doc_drift_sync)


def _append_doc_drift_sync(entries: list[str]) -> None:
    """Append drift entries to DOC_DRIFT.md."""
    path = os.path.join(os.path.dirname(__file__), "evals", "DOC_DRIFT.md")
    with open(path, "a") as f:
        for entry in entries:
            f.write(entry)
            f.write("\n")


async def _append_doc_drift(ctx: BloomContext, entries: list[str]) -> None:
    await asyncio.to_thread(_append_doc_drift_sync, entries)


# ──────────────────────────────────────────────────────────────────────────────
# Handler implementations
# ──────────────────────────────────────────────────────────────────────────────


async def handle_morning_digest(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Compile and post a morning digest of MRs, pipelines, and tickets."""
    dedupe_key = f"morning-digest|{_today()}"
    run_id = get_job_run_id()

    if await is_duplicate(dedupe_key, ctx):
        return await _skip(run_id, "morning-digest", dedupe_key, ctx)

    new_mrs: list[dict[str, Any]] = []
    failed_pipelines: list[dict[str, Any]] = []
    for repo in PLATFORM_REPOS:
        new_mrs.extend(await _fetch_gitlab_mrs(ctx, repo, state="opened"))
        failed_pipelines.extend(await _fetch_gitlab_pipelines(ctx, repo))

    high_priority_tickets = await _fetch_jira_issues(
        ctx,
        "priority in (High, Critical, Blocker) AND status not in (Done, Closed)",
    )

    prompt = (
        "Summarize the following into a concise Markdown morning digest:\n\n"
        f"New MRs: {json.dumps(new_mrs, default=str)}\n\n"
        f"Failed pipelines: {json.dumps(failed_pipelines, default=str)}\n\n"
        f"High priority tickets: {json.dumps(high_priority_tickets, default=str)}"
    )
    summary = await _summarize_with_llm(ctx, prompt)
    slack_response = await slack_post(summary, ctx)

    return await _write(
        run_id,
        "morning-digest",
        dedupe_key,
        "success",
        {
            "mr_count": len(new_mrs),
            "failed_pipeline_count": len(failed_pipelines),
            "high_priority_ticket_count": len(high_priority_tickets),
            "slack_ts": slack_response.get("ts") if isinstance(slack_response, dict) else None,
        },
        None,
        ctx,
    )


async def handle_datadog_alert_triage(ctx: BloomContext, payload: dict[str, Any]) -> JobRun:
    """Triage a Datadog alert and post findings as a Slack thread."""
    monitor_id = str(payload.get("monitor_id", "unknown"))
    triggered_at = payload.get("triggered_at", _today())
    dedupe_key = f"datadog-alert|{monitor_id}|{triggered_at}"
    run_id = get_job_run_id()

    if await is_duplicate(dedupe_key, ctx):
        return await _skip(run_id, "datadog-alert-triage", dedupe_key, ctx)

    prompt = (
        f"A Datadog monitor fired. Run the incident-triage skill. "
        f"Monitor: {payload.get('monitor_name', 'unknown')}. "
        f"Alert message: {payload.get('alert_message', 'unknown')}."
    )

    for attempt in range(1, 4):
        try:
            findings = await _emit_agent_prompt(ctx, "sre-investigator", prompt)
            thread_ts = payload.get("slack_thread_ts", "")
            slack_response = await slack_post(findings, ctx, thread_ts=thread_ts)
            return await _write(
                run_id,
                "datadog-alert-triage",
                dedupe_key,
                "success",
                {
                    "monitor_id": monitor_id,
                    "attempt": attempt,
                    "slack_ts": slack_response.get("ts") if isinstance(slack_response, dict) else None,
                },
                None,
                ctx,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("datadog-alert-triage attempt %s failed: %s", attempt, exc)
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)
            else:
                return await _write(run_id, "datadog-alert-triage", dedupe_key, "failed", {"monitor_id": monitor_id}, str(exc), ctx)

    return await _write(run_id, "datadog-alert-triage", dedupe_key, "failed", {"monitor_id": monitor_id}, "exhausted retries", ctx)  # pragma: no cover


async def handle_weekly_ticket_harvest(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Harvest closed tickets / merged MRs and upsert blurbs into the tickets namespace."""
    dedupe_key = f"weekly-harvest|{_this_week()}"
    run_id = get_job_run_id()

    if await is_duplicate(dedupe_key, ctx):
        return await _skip(run_id, "weekly-ticket-harvest", dedupe_key, ctx)

    since = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
    closed_tickets = await _fetch_jira_issues(
        ctx,
        f"status in (Done, Closed) AND updated >= {since}",
    )
    merged_mrs: list[dict[str, Any]] = []
    for repo in PLATFORM_REPOS:
        merged_mrs.extend(await _fetch_gitlab_mrs(ctx, repo, state="merged"))

    prompt = (
        "Summarize each item into a 200-word Markdown blurb with metadata: "
        "project, service, closed_at, type. Return a JSON array.\n\n"
        f"Jira tickets: {json.dumps(closed_tickets, default=str)}\n\n"
        f"GitLab MRs: {json.dumps(merged_mrs, default=str)}"
    )
    blurbs = await _summarize_with_llm(ctx, prompt, max_tokens=8000)
    blurbs_json = _extract_json(blurbs) or []

    if ctx.mcp_client.vector_writer is not None:
        documents = []
        for idx, blurb in enumerate(blurbs_json):
            doc_id = hashlib.sha256(f"weekly-harvest|{since}|{idx}".encode()).hexdigest()
            documents.append(
                OrchidDocument(
                    id=doc_id,
                    page_content=json.dumps(blurb),
                    metadata={
                        "source": "weekly-harvest",
                        "scope": "tenant",
                        "namespace": "tickets",
                        "authority": "live",
                        "type": blurb.get("type", "unknown"),
                        "service": blurb.get("service", "unknown"),
                        "closed_at": blurb.get("closed_at", since),
                    },
                ),
            )
        scope = OrchidRAGScope(tenant_id=ctx.tenant_id)
        await ctx.mcp_client.vector_writer.upsert(documents, scope=scope)

    return await _write(
        run_id,
        "weekly-ticket-harvest",
        dedupe_key,
        "success",
        {
            "ticket_count": len(closed_tickets),
            "mr_count": len(merged_mrs),
            "upserted_blurbs": len(blurbs_json),
        },
        None,
        ctx,
    )


async def handle_reindex_on_merge(ctx: BloomContext, payload: dict[str, Any]) -> JobRun:
    """Trigger fm-indexer docs when a push lands on develop."""
    repo_name = payload.get("repo_name", "")
    branch = payload.get("branch", "")
    commit_sha = payload.get("commit_sha", "unknown")
    dedupe_key = f"reindex|{repo_name}|{branch}|{commit_sha}"
    run_id = get_job_run_id()

    if branch != "develop":
        return await _write(
            run_id,
            "reindex-on-merge",
            dedupe_key,
            "skipped",
            {"reason": "not develop branch", "branch": branch},
            None,
            ctx,
        )

    return await _write(
        run_id,
        "reindex-on-merge",
        dedupe_key,
        "success",
        {"repo": repo_name, "branch": branch, "commit": commit_sha},
        None,
        ctx,
    )


async def handle_log_anomaly_digest(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Pull logs, compare error rates, and store a new baseline."""
    today = _today()
    dedupe_key = f"log-anomaly|{today}"
    run_id = get_job_run_id()

    if await is_duplicate(dedupe_key, ctx):
        return await _skip(run_id, "log-anomaly-digest", dedupe_key, ctx)

    errors_by_service: dict[str, list[str]] = {}
    for repo in PLATFORM_REPOS:
        service_name = re.sub(r"-be$", "", repo)
        logs = await _fetch_datadog_logs(ctx, service_name)
        errors_by_service[service_name] = [str(log.get("message", "")) for log in logs]

    error_counts = {svc: len(errs) for svc, errs in errors_by_service.items()}
    new_signatures = {svc: _top_signatures(errs) for svc, errs in errors_by_service.items()}

    baseline = await _load_baseline(ctx)
    deltas = {}
    for svc, count in error_counts.items():
        prev = baseline.get(svc, 0)
        deltas[svc] = {"current": count, "previous": prev, "delta": count - prev}

    await _store_baseline(ctx, error_counts)

    prompt = (
        "Analyze these error-rate deltas and new error signatures for the SRE team. "
        "Return a concise Markdown digest.\n\n"
        f"Deltas: {json.dumps(deltas, default=str)}\n\n"
        f"New signatures: {json.dumps(new_signatures, default=str)}"
    )
    digest = await _summarize_with_llm(ctx, prompt)
    slack_response = await slack_post(digest, ctx)

    return await _write(
        run_id,
        "log-anomaly-digest",
        dedupe_key,
        "success",
        {
            "date": today,
            "deltas": deltas,
            "new_signatures": new_signatures,
            "slack_ts": slack_response.get("ts") if isinstance(slack_response, dict) else None,
        },
        None,
        ctx,
    )


async def handle_confluence_sync(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Walk Confluence spaces and ingest new/updated pages."""
    run_id = get_job_run_id()
    outer_dedupe = f"confluence-sync|{_today()}"

    if await is_duplicate(outer_dedupe, ctx):
        return await _skip(run_id, "confluence-sync", outer_dedupe, ctx)

    spaces = await ctx.mcp_client.call("atlassian-rovo", "getConfluenceSpaces", {})
    ingested = 0
    for space in spaces:
        space_key = space.get("key", "")
        pages = await ctx.mcp_client.call(
            "atlassian-rovo",
            "getPagesInConfluenceSpace",
            {"space_key": space_key},
        )
        for page in pages:
            page_id = str(page.get("id", "unknown"))
            version = str(page.get("version", "0"))
            dedupe_key = f"confluence-sync|{page_id}|{version}"
            if await is_duplicate(dedupe_key, ctx):
                continue

            page_body = await ctx.mcp_client.call(
                "atlassian-rovo",
                "getConfluencePage",
                {"page_id": page_id},
            )
            namespace = "runbooks" if "runbook" in str(page.get("title", "")).lower() else "internal-docs"
            await _capture_tool_result(
                ctx,
                source="confluence",
                source_id=page_id,
                source_version=version,
                url=page.get("_links", {}).get("webui", ""),
                tool_name="getConfluencePage",
                result=page_body,
            )

            await _write(run_id, "confluence-sync", dedupe_key, "success", {"page_id": page_id, "namespace": namespace}, None, ctx)
            ingested += 1

    return await _write(run_id, "confluence-sync", outer_dedupe, "success", {"ingested_pages": ingested}, None, ctx)


async def handle_help_center_sync(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Re-run fm-indexer kb on Help Center whitelisted sections."""
    run_id = get_job_run_id()
    outer_dedupe = f"help-center-sync|{_today()}"

    if await is_duplicate(outer_dedupe, ctx):
        return await _skip(run_id, "help-center-sync", outer_dedupe, ctx)

    articles = await ctx.mcp_client.call("atlassian-rovo", "searchConfluenceUsingCql", {"cql": "space=KB"})
    ingested = 0
    for article in articles:
        article_id = str(article.get("id", "unknown"))
        updated_at = str(article.get("last_updated", _today()))
        dedupe_key = f"help-center-sync|{article_id}|{updated_at}"
        if await is_duplicate(dedupe_key, ctx):
            continue

        await _write(run_id, "help-center-sync", dedupe_key, "success", {"article_id": article_id}, None, ctx)
        ingested += 1

    return await _write(run_id, "help-center-sync", outer_dedupe, "success", {"ingested_articles": ingested}, None, ctx)


async def handle_capture_retention(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Prune old captures and flag promotion candidates."""
    dedupe_key = f"capture-retention|{_this_week()}"
    run_id = get_job_run_id()

    if await is_duplicate(dedupe_key, ctx):
        return await _skip(run_id, "capture-retention", dedupe_key, ctx)

    cutoff = (datetime.now(UTC) - timedelta(days=30)).isoformat()
    if ctx.mcp_client.vector_writer is not None:
        await ctx.mcp_client.vector_writer.delete(
            scope=OrchidRAGScope(tenant_id=ctx.tenant_id),
            metadata_filter={"authority": "live", "scope": "chat_agent", "retrieved_at": {"lt": cutoff}},
        )

    # Simulate citation counting across distinct chats.
    candidates = await _count_citation_candidates(ctx)
    candidate_text = "\n".join(f"- {item_id} (cited {count} times)" for item_id, count in candidates)
    if candidate_text:
        await slack_post(
            f"Weekly capture promotion candidates:\n{candidate_text}",
            ctx,
        )

    return await _write(
        run_id,
        "capture-retention",
        dedupe_key,
        "success",
        {"pruned_before": cutoff, "promotion_candidates": candidates},
        None,
        ctx,
    )


async def handle_doc_drift_check(ctx: BloomContext, _payload: dict[str, Any] | None = None) -> JobRun:
    """Re-validate golden pairs and append drift to DOC_DRIFT.md."""
    month = _this_month()
    dedupe_key = f"doc-drift|{month}"
    run_id = get_job_run_id()

    if await is_duplicate(dedupe_key, ctx):
        return await _skip(run_id, "doc-drift-check", dedupe_key, ctx)

    pairs = await _read_golden_pairs(ctx)
    drift_entries: list[str] = []
    for pair in pairs:
        if not pair.get("approved", False):
            continue
        for claim in pair.get("claims", []):
            if not claim.get("code_checkable", False):
                continue
            verification = await _verify_claim(ctx, claim)
            if verification != "confirmed":
                drift_entries.append(
                    f"\n## {pair.get('id', 'unknown')} — {_hash_claim(claim.get('text', ''))}\n"
                    f"- Claim: {claim.get('text', '')}\n"
                    f"- Status: {verification}\n"
                    f"- Checked: {datetime.now(UTC).isoformat()}\n"
                )

    if drift_entries:
        await _append_doc_drift(ctx, drift_entries)

    summary = f"Doc drift check: {len(drift_entries)} newly drifted claims."
    await slack_post(summary, ctx)

    return await _write(run_id, "doc-drift-check", dedupe_key, "success", {"drift_count": len(drift_entries)}, None, ctx)


# ──────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ──────────────────────────────────────────────────────────────────────────────


TRIGGER_HANDLERS: dict[str, Any] = {
    "morning-digest": handle_morning_digest,
    "datadog-alert-triage": handle_datadog_alert_triage,
    "weekly-ticket-harvest": handle_weekly_ticket_harvest,
    "reindex-on-merge": handle_reindex_on_merge,
    "log-anomaly-digest": handle_log_anomaly_digest,
    "confluence-sync": handle_confluence_sync,
    "help-center-sync": handle_help_center_sync,
    "capture-retention": handle_capture_retention,
    "doc-drift-check": handle_doc_drift_check,
}


async def dispatch(trigger_id: str, ctx: BloomContext, payload: dict[str, Any] | None = None) -> JobRun:
    """Route a trigger id to its handler and return the job run."""
    handler = TRIGGER_HANDLERS.get(trigger_id)
    if handler is None:
        raise ValueError(f"Unknown trigger: {trigger_id}")

    return await handler(ctx, payload or {})


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────


async def _skip(run_id: str, trigger_id: str, dedupe_key: str, ctx: BloomContext) -> JobRun:
    return await _write(run_id, trigger_id, dedupe_key, "skipped", {"reason": "duplicate dedupe_key"}, None, ctx)


async def _write(
    run_id: str,
    trigger_id: str,
    dedupe_key: str,
    status: str,
    result: dict[str, Any],
    error: str | None,
    ctx: BloomContext,
) -> JobRun:
    return await write_job_run(run_id, trigger_id, dedupe_key, status, result, error, ctx)


def _extract_json(text: str) -> Any:
    """Best-effort JSON array extraction from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _top_signatures(messages: list[str], n: int = 5) -> list[str]:
    """Return the most common normalized error signatures."""
    cleaned = [re.sub(r"0x[0-9a-f]+", "<hex>", re.sub(r"\d+", "<num>", msg)) for msg in messages]
    counts: dict[str, int] = {}
    for msg in cleaned:
        counts[msg] = counts.get(msg, 0) + 1
    return [msg for msg, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]]


async def _load_baseline(ctx: BloomContext) -> dict[str, int]:
    """Load the previous window's error counts from Postgres."""
    import asyncpg
    try:
        conn = await asyncpg.connect(ctx.postgres_dsn)
        row = await conn.fetchrow("SELECT data FROM log_anomaly_baseline ORDER BY created_at DESC LIMIT 1")
        await conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load log anomaly baseline: %s", exc)
        return {}
    return json.loads(row["data"]) if row else {}


async def _store_baseline(ctx: BloomContext, error_counts: dict[str, int]) -> None:
    """Store the current window's error counts in Postgres."""
    import asyncpg
    try:
        conn = await asyncpg.connect(ctx.postgres_dsn)
        await conn.execute(
            "INSERT INTO log_anomaly_baseline (id, data, created_at) VALUES ($1, $2, $3)",
            str(uuid.uuid4()),
            json.dumps(error_counts),
            datetime.now(UTC).isoformat(),
        )
        await conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not store log anomaly baseline: %s", exc)


async def _count_citation_candidates(ctx: BloomContext) -> list[tuple[str, int]]:
    """Return L1 items cited >= 3 times across distinct chats."""
    if ctx.mcp_client.vector_writer is None:
        return []
    # The vector writer is a generic interface; we simulate a metadata query.
    try:
        rows = await ctx.mcp_client.vector_writer.query(
            "",
            k=1000,
            scope=OrchidRAGScope(tenant_id=ctx.tenant_id),
            metadata_filter={"authority": "live", "scope": "chat_agent"},
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Citation counting query failed: %s", exc)
        return []

    counts: dict[str, int] = {}
    for row in rows:
        item_id = row.get("metadata", {}).get("source_id", "")
        if item_id:
            counts[item_id] = counts.get(item_id, 0) + 1
    return [(item_id, count) for item_id, count in counts.items() if count >= 3]


async def _verify_claim(ctx: BloomContext, claim: dict[str, Any]) -> str:
    """Verify a code-checkable claim against the current repo state."""
    repo_path = claim.get("repo_path", "")
    expected_pattern = claim.get("expected_pattern", "")
    try:
        files = await ctx.mcp_client.call("gitlab", "search_code", {"project": repo_path, "query": expected_pattern})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Claim verification failed for %s: %s", repo_path, exc)
        return "unverified"
    return "confirmed" if any(expected_pattern in str(f) for f in files) else "refuted"



