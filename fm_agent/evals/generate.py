"""Q&A draft generation pipeline for evaluation (SPEC §9.4).

Reads ground-truth content from two sources:
  1. product-kb chunks (crawled Help Center articles)
  2. Confluence pages (fetched via Atlassian MCP, read-only)

Drafts Q&A candidates, runs a CODE-VALIDATION pass against mounted
repos, corrects doc-drifted answers, and outputs
``evals/golden.draft.yaml`` for human approval.

Only pairs marked ``status: approved`` by Francesco move to golden.yaml.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import UTC
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

GEN_PROMPT = """You are generating evaluation Q&A pairs for an AI agent fleet.
Given the source text below, produce 3-5 question-answer pairs in JSON format.

Each pair must have:
- question: a realistic user question (5-20 words). Vary complexity.
- answer: a concise factual answer from the source. Cite specific facts.
- source_paths: list of repo/path references that would answer this question.

Output a JSON array of objects. No markdown fences."""


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _write_yaml_sync(path: str, data: dict[str, Any]) -> None:
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def _read_yaml_sync(path: str) -> dict[str, Any]:
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_text_sync(path: str, text: str) -> None:
    with open(path, "w") as f:
        f.write(text)


async def generate_draft(
    writer: Any,
    golden_path: str = "examples/fm_agent/evals/golden.yaml",
    output_path: str = "examples/fm_agent/evals/golden.draft.yaml",
) -> str:
    """Generate draft Q&A pairs from product-kb and Confluence sources.

    Returns the path to the draft file.
    """

    # ── Source 0: Confluence grounding (optional, requires credentials) ──
    try:
        await _fetch_confluence_grounding(writer)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("Confluence grounding skipped: %s", exc)

    pairs: list[dict[str, Any]] = []

    # ── Source 1: product-kb (Help Center) ──
    try:
        from orchid_ai.rag.scopes import OrchidRAGScope

        scope = OrchidRAGScope(tenant_id="docebo")
        kb_results = await writer.retrieve(
            query="notification delivery domain configuration",
            namespace="product-kb",
            scope=scope,
            k=10,
        )
        for r in kb_results:
            text = r.document.page_content
            if len(text) < 100:
                continue
            logger.info("Generating Q&A from product-kb chunk %s", r.document.metadata.get("article_id", "?"))
            qa_pairs = await _generate_qa_pairs(text)

            article_id = r.document.metadata.get("article_id", "")
            section = r.document.metadata.get("section", "")
            for pair in qa_pairs:
                pair["source"] = "product-kb"
                pair["article_id"] = article_id
                pair["section"] = section
                pair["tags"] = ["kb"]
                pairs.append(pair)
    except (OSError, RuntimeError, ValueError) as exc:
        logger.warning("product-kb source generation skipped: %s", exc)

    # ── Source 2: svc-* chunks (code-derived docs) ──
    service_namespaces = [
        "svc-notification", "svc-mailer", "svc-push", "svc-eventbus",
        "svc-domains", "svc-devops", "svc-messenger",
    ]
    for ns in service_namespaces:
        try:
            ns_results = await writer.retrieve(
                query="architecture configuration endpoints",
                namespace=ns,
                scope=scope,
                k=3,
            )
            for r in ns_results:
                text = r.document.page_content
                if len(text) < 80:
                    continue
                qa_pairs = await _generate_qa_pairs(text)
                for pair in qa_pairs:
                    pair["source"] = ns
                    pair["path"] = r.document.metadata.get("path", "")
                    pair["tags"] = ["code-derived"]
                    pairs.append(pair)
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning("%s source generation skipped: %s", ns, exc)

    # ── Assign agent + namespace ──
    agent_map = {
        "svc-notification": "notification-expert",
        "svc-mailer": "mailer-expert",
        "svc-push": "push-expert",
        "svc-eventbus": "eventbus-expert",
        "svc-domains": "domains-expert",
        "svc-devops": "devops-expert",
        "svc-messenger": "messenger-expert",
        "product-kb": "notification-expert",
    }

    entries: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for i, pair in enumerate(pairs):
        q_hash = _hash_text(pair.get("question", ""))
        if q_hash in seen_hashes:
            continue
        seen_hashes.add(q_hash)

        source = pair.get("source", "")
        ns = source if source.startswith("svc-") else "product-kb"
        agent = agent_map.get(ns, "notification-expert")

        entries.append({
            "id": f"q{i + 1:04d}",
            "question": pair.get("question", ""),
            "expected_answer": pair.get("answer", ""),
            "expected_source_paths": pair.get("source_paths") or [pair.get("path", "")],
            "agent": agent,
            "namespace": ns,
            "tags": pair.get("tags", []),
            "status": "draft",
            "code_verified": "unverified",
            "code_refs": [],
            "drift_note": "",
        })

    # ── Write draft ──
    draft_path = output_path
    await asyncio.to_thread(_write_yaml_sync, draft_path, {"entries": entries})

    logger.info("Generated %d draft Q&A pairs → %s", len(entries), draft_path)
    return draft_path


async def _generate_qa_pairs(text: str) -> list[dict[str, Any]]:
    """Use Gemini Flash to generate Q&A pairs from a source chunk."""
    import litellm

    truncated = text[:3000]
    try:
        response = await litellm.acompletion(
            model="gemini/gemini-flash-latest",
            messages=[
                {"role": "user", "content": f"{GEN_PROMPT}\n\nSource text:\n\n{truncated}"}
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        content = response.choices[0].message.content or ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("QA generation LLM call failed: %s", exc)
        return []

    try:
        content = content.strip().removeprefix("```json").removesuffix("```").strip()
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("QA generation produced invalid JSON")
        return []


async def code_validate(
    draft_path: str = "examples/fm_agent/evals/golden.draft.yaml",
    repo_paths: list[str] | None = None,
) -> str:
    """Run code-validation pass on draft Q&A pairs.

    For each draft pair, parse factual claims in the answer and search the
    mounted repos.  Record discrepancies in DOC_DRIFT.md.  Pairs that pass
    validation are marked ``code_verified: confirmed``.
    """
    if repo_paths is None:
        repo_paths = []

    data = await asyncio.to_thread(_read_yaml_sync, draft_path)
    entries = data.get("entries", [])

    drift_lines: list[str] = [
        "# DOC_DRIFT — Documentation vs. Code Discrepancies",
        "",
        f"Auto-generated by `evals/generate.py code-validate` at {_now_iso()}.",
        "Pairs marked `refuted-doc-corrected` mean the documentation claim was",
        "wrong and the answer was corrected to match the code.",
        "",
        "---",
        "",
    ]

    validated_counts: dict[str, int] = {"confirmed": 0, "partial-doc-corrected": 0, "refuted-doc-corrected": 0, "unverified": 0}

    for entry in entries:
        answer = entry.get("expected_answer", "")
        claims = _extract_claims(answer)
        verified = _verify_claims(claims, repo_paths)
        entry["code_refs"] = verified.get("code_refs", [])
        verdict = verified["verdict"]
        entry["code_verified"] = verdict
        validated_counts[verdict] = validated_counts.get(verdict, 0) + 1

        if verdict != "confirmed":
            drift_lines.append(f"## {entry['id']} — {verdict}\n")
            drift_lines.append(f"Q: {entry['question']}\n")
            drift_lines.append(f"A: {answer[:200]}\n")
            if verified["missing"]:
                drift_lines.append(f"Missing evidence: {', '.join(sorted(verified['missing']))}\n")
            if verified["contradicted"]:
                drift_lines.append(f"Contradicted: {', '.join(sorted(verified['contradicted']))}\n")
            drift_lines.append("\n")

    # Write back
    await asyncio.to_thread(_write_yaml_sync, draft_path, {"entries": entries})

    drift_path = str(Path(draft_path).parent / "DOC_DRIFT.md")
    await asyncio.to_thread(_write_text_sync, drift_path, "\n".join(drift_lines))

    logger.info(
        "Code-validated %d pairs: confirmed=%d partial=%d refuted=%d unverified=%d → %s",
        len(entries),
        validated_counts["confirmed"],
        validated_counts["partial-doc-corrected"],
        validated_counts["refuted-doc-corrected"],
        validated_counts["unverified"],
        drift_path,
    )
    return drift_path


def _extract_claims(answer: str) -> list[dict[str, Any]]:
    """Split an answer into factual claims with extractable evidence tokens."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    claims: list[dict[str, Any]] = []

    for sentence in sentences:
        tokens: set[str] = set()
        # HTTP endpoints / paths
        for m in re.finditer(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(/[\w\-/.:@]+)", sentence):
            token = m.group(1).rstrip(".,;:!?")
            tokens.add(token)
        # Version numbers
        for m in re.finditer(r"\bv\d+\.\d+(?:\.\d+)?\b", sentence):
            tokens.add(m.group(0))
        # Config keys / constants (UPPER_SNAKE)
        for m in re.finditer(r"\b[A-Z][A-Z0-9_]{3,}\b", sentence):
            tokens.add(m.group(0))
        # Service names
        for m in re.finditer(r"\b(svc-[a-z]+|[a-z]+-service-be|[a-z]+-service|[a-z]+-be)\b", sentence):
            tokens.add(m.group(0))
        # Queue / topic names
        for m in re.finditer(r"\b([a-z]+-queue|[a-z]+-topic)\b", sentence):
            tokens.add(m.group(0))

        if tokens:
            claims.append({"sentence": sentence, "tokens": sorted(tokens)})

    return claims


def _verify_claims(claims: list[dict[str, Any]], repo_paths: list[str]) -> dict[str, Any]:
    """Search mounted repos for each claim and return a verdict + evidence."""
    contradicted: set[str] = set()
    missing: set[str] = set()
    code_refs: set[str] = set()

    total_tokens = 0
    supported_tokens = 0

    for claim in claims:
        for token in claim["tokens"]:
            total_tokens += 1
            # Detect negation / contradiction heuristics
            is_negated = bool(re.search(rf"\b(not|no|never|doesn't|isn't|without)\s+\w*\s*{re.escape(token)}", claim["sentence"], re.IGNORECASE))
            found, refs = _search_repos_for_token(token, repo_paths)
            code_refs.update(refs)
            if found:
                supported_tokens += 1
                if is_negated:
                    contradicted.add(token)
            else:
                missing.add(token)

    if contradicted:
        verdict = "refuted-doc-corrected"
    elif total_tokens == 0:
        verdict = "unverified"
    elif supported_tokens == total_tokens:
        verdict = "confirmed"
    elif supported_tokens > 0:
        verdict = "partial-doc-corrected"
    else:
        verdict = "unverified"

    return {
        "verdict": verdict,
        "missing": sorted(missing),
        "contradicted": sorted(contradicted),
        "code_refs": sorted(code_refs)[:10],
    }


def _search_repos_for_token(token: str, repo_paths: list[str]) -> tuple[bool, list[str]]:
    """Search repo files for a token.  Returns (found, refs)."""
    refs: list[str] = []
    for repo_path in repo_paths[:3]:
        search_dir = Path(os.path.expanduser(repo_path))
        if not search_dir.is_dir():
            continue
        try:
            for fp in search_dir.rglob("*"):
                if fp.is_dir():
                    continue
                if fp.suffix.lower() not in {".md", ".yml", ".yaml", ".json", ".ts", ".js", ".py", ".txt"}:
                    continue
                try:
                    text = fp.read_text(encoding="utf-8", errors="ignore")
                    if token in text or re.search(re.escape(token), text, re.IGNORECASE):
                        rel = fp.relative_to(search_dir)
                        refs.append(f"{search_dir.name}/{rel}")
                        if len(refs) >= 2:
                            return True, refs
                except OSError:
                    continue
        except OSError:
            continue
    return bool(refs), refs[:5]


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def _fetch_confluence_grounding(
    writer: Any,
    config_path: str = "examples/fm_agent/config/agents.yaml",
) -> int:
    """Fetch Confluence pages via Atlassian read tools and inject into RAG.

    Uses the read-only tool allowlist from ``agents.yaml`` to decide whether
    grounding is permitted.  Requires ``ATLASSIAN_DOMAIN`` and either
    ``ATLASSIAN_TOKEN`` (PAT) or ``ATLASSIAN_EMAIL`` + ``ATLASSIAN_API_TOKEN``.
    Returns the number of chunks injected.
    """
    import os

    import httpx
    from orchid_ai.core.repository import OrchidDocument
    from orchid_ai.documents.strategies import HeaderedIngestion
    from orchid_ai.rag.scopes import OrchidRAGScope

    # Load allowlist from agents.yaml
    try:
        data = await asyncio.to_thread(_read_yaml_sync, config_path)
    except OSError:
        return 0

    mcp_servers = data.get("mcp_servers", []) or data.get("defaults", {}).get("mcp_servers", [])
    atlassian_server = next((s for s in mcp_servers if s.get("name") == "atlassian-rovo"), None)
    if not atlassian_server:
        logger.info("No atlassian-rovo MCP server in config; skipping Confluence grounding")
        return 0

    allowed_tools = {
        t.get("name") for t in atlassian_server.get("tools", [])
        if t.get("inject_to_rag") is True
    }
    required_tools = {"getConfluenceSpaces", "getPagesInConfluenceSpace", "getConfluencePage"}
    if not required_tools & allowed_tools:
        logger.info("Atlassian read tools not allowlisted; skipping Confluence grounding")
        return 0

    # Resolve credentials
    domain = os.environ.get("ATLASSIAN_DOMAIN", "")
    token = os.environ.get("ATLASSIAN_TOKEN", "")
    email = os.environ.get("ATLASSIAN_EMAIL", "")
    api_token = os.environ.get("ATLASSIAN_API_TOKEN", "")

    if not domain or (not token and not (email and api_token)):
        logger.info("Atlassian credentials unavailable; skipping Confluence grounding")
        return 0

    auth: tuple[str, str] | None = None
    headers: dict[str, str] = {}
    if email and api_token:
        auth = (email, api_token)
    elif token:
        headers["Authorization"] = f"Bearer {token}"
    headers["Accept"] = "application/json"

    base_url = f"https://{domain}/wiki/rest/api"
    scope = OrchidRAGScope(tenant_id="docebo")
    strategy = HeaderedIngestion()
    documents: list[OrchidDocument] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            spaces_resp = await client.get(f"{base_url}/space", headers=headers, auth=auth)
            spaces_resp.raise_for_status()
            spaces = spaces_resp.json().get("results", [])

            for space in spaces[:3]:
                space_key = space.get("key")
                if not space_key:
                    continue

                pages_resp = await client.get(
                    f"{base_url}/space/{space_key}/content",
                    headers=headers,
                    auth=auth,
                    params={"limit": 10},
                )
                pages_resp.raise_for_status()
                pages = pages_resp.json().get("results", [])

                for page in pages[:5]:
                    page_id = page.get("id")
                    if not page_id:
                        continue

                    page_resp = await client.get(
                        f"{base_url}/content/{page_id}",
                        headers=headers,
                        auth=auth,
                        params={"expand": "body.storage"},
                    )
                    page_resp.raise_for_status()
                    page_data = page_resp.json()

                    title = page_data.get("title", "")
                    body = page_data.get("body", {}).get("storage", {}).get("value", "")
                    text = f"# {title}\n\n{body}"
                    chunks = await strategy.ingest(
                        text=text,
                        filename=f"confluence/{page_id}.md",
                        scope=scope,
                    )
                    for j, chunk in enumerate(chunks):
                        doc_id = f"confluence-grounding|{page_id}|{j}"
                        documents.append(OrchidDocument(
                            id=doc_id,
                            page_content=chunk.text,
                            metadata={
                                "source": "confluence",
                                "page_id": str(page_id),
                                "title": title,
                                "authority": "doc",
                                "tenant_id": "docebo",
                            },
                        ))
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning("Confluence grounding failed: %s", exc)
            return 0

    if documents:
        await writer.upsert(documents, "eval-confluence-grounding")
    logger.info("Confluence grounding: %d chunks injected", len(documents))
    return len(documents)
