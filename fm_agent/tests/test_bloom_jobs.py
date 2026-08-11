"""Tests for Pollen/Bloom job handlers."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from examples.fm_agent.bloom_jobs import (
    PLATFORM_REPOS,
    BloomContext,
    InMemoryJobRunStore,
    MCPClient,
    dispatch,
    handle_capture_retention,
    handle_confluence_sync,
    handle_datadog_alert_triage,
    handle_doc_drift_check,
    handle_help_center_sync,
    handle_log_anomaly_digest,
    handle_morning_digest,
    handle_reindex_on_merge,
    handle_weekly_ticket_harvest,
    is_duplicate,
    slack_post,
)


def _make_context(**overrides: object) -> BloomContext:
    """Build a BloomContext with no-op but inspectable dependencies."""
    store = InMemoryJobRunStore()
    vector_writer = AsyncMock()
    vector_writer.upsert = AsyncMock()
    vector_writer.delete = AsyncMock()
    vector_writer.query = AsyncMock(return_value=[])

    llm_complete = AsyncMock(return_value="LLM summary")
    invoke_agent = AsyncMock(return_value="agent findings")

    async def call_tool(server: str, tool: str, params: dict | None = None) -> object:
        return {
            ("gitlab", "list_merge_requests"): [{"iid": 1, "title": "MR", "repo": params.get("repo")}],
            ("gitlab", "list_pipelines"): [{"id": 1, "status": "failed", "repo": params.get("repo")}],
            ("gitlab", "search_code"): [{"path": "src/main.py"}],
            ("atlassian-rovo", "searchJiraIssuesUsingJql"): [{"key": "PROJ-1"}],
            ("atlassian-rovo", "getConfluenceSpaces"): [{"key": "DOC"}],
            ("atlassian-rovo", "getPagesInConfluenceSpace"): [{"id": 101, "title": "Runbook", "version": 3, "_links": {"webui": "https://wiki.example.com/101"}}],
            ("atlassian-rovo", "getConfluencePage"): {"body": "page content"},
            ("atlassian-rovo", "searchConfluenceUsingCql"): [{"id": 201, "last_updated": "2024-01-01"}],
            ("datadog", "query_logs"): [{"message": "NullPointerException"}],
            ("slack", "chat_postMessage"): {"ts": "12345.6789"},
        }.get((server, tool), [])

    mcp = MCPClient(
        call_tool=call_tool,
        invoke_agent=invoke_agent,
        vector_writer=vector_writer,
        llm_complete=llm_complete,
    )
    return BloomContext(
        tenant_id="test-tenant",
        job_store=store,
        mcp_client=mcp,
        slack_channel="#test",
        postgres_dsn="postgresql://noop",
    )


class TestIsDuplicate:
    async def test_returns_true_for_existing_success(self) -> None:
        ctx = _make_context()
        run_id = "run-1"
        await ctx.job_store.write(
            type("JobRun", (), {
                "id": run_id,
                "trigger_id": "t",
                "dedupe_key": "key-1",
                "status": "success",
                "result": {},
                "error": None,
                "created_at": None,
            })(),
        )
        assert await is_duplicate("key-1", ctx) is True

    async def test_returns_false_for_failed_run(self) -> None:
        ctx = _make_context()
        await ctx.job_store.write(
            type("JobRun", (), {
                "id": "run-1",
                "trigger_id": "t",
                "dedupe_key": "key-1",
                "status": "failed",
                "result": {},
                "error": None,
                "created_at": None,
            })(),
        )
        assert await is_duplicate("key-1", ctx) is False


class TestSlackPost:
    async def test_posts_to_configured_channel(self) -> None:
        ctx = _make_context()
        result = await slack_post("hello", ctx)
        assert result == {"ts": "12345.6789"}

    async def test_passes_thread_ts_when_given(self) -> None:
        ctx = _make_context()
        result = await slack_post("reply", ctx, thread_ts="12345.6789")
        assert result == {"ts": "12345.6789"}


class TestMorningDigest:
    async def test_queries_all_repos_and_posts_summary(self) -> None:
        ctx = _make_context()
        run = await handle_morning_digest(ctx)
        assert run.status == "success"
        assert run.result["mr_count"] == len(PLATFORM_REPOS)
        assert run.result["failed_pipeline_count"] == len(PLATFORM_REPOS)
        assert run.result["high_priority_ticket_count"] == 1
        assert run.result["slack_ts"] == "12345.6789"


class TestDatadogAlertTriage:
    async def test_runs_skill_and_posts_thread(self) -> None:
        ctx = _make_context()
        payload = {
            "monitor_id": "mon-1",
            "triggered_at": "2024-01-01T00:00:00Z",
            "monitor_name": "High Error Rate",
            "alert_message": "Errors spiking",
            "slack_thread_ts": "1111.2222",
        }
        run = await handle_datadog_alert_triage(ctx, payload)
        assert run.status == "success"
        assert run.result["monitor_id"] == "mon-1"
        assert run.result["slack_ts"] == "12345.6789"

    async def test_skips_duplicate(self) -> None:
        ctx = _make_context()
        payload = {"monitor_id": "mon-1", "triggered_at": "2024-01-01T00:00:00Z"}
        await handle_datadog_alert_triage(ctx, payload)
        second = await handle_datadog_alert_triage(ctx, payload)
        assert second.status == "skipped"


class TestWeeklyTicketHarvest:
    async def test_harvests_and_upserts_blurbs(self) -> None:
        ctx = _make_context()
        ctx.mcp_client.llm_complete = AsyncMock(
            return_value=json.dumps([{"project": "P", "service": "svc", "closed_at": "2024-01-01", "type": "ticket"}]),
        )
        run = await handle_weekly_ticket_harvest(ctx)
        assert run.status == "success"
        assert run.result["ticket_count"] == 1
        assert run.result["mr_count"] == len(PLATFORM_REPOS)
        assert run.result["upserted_blurbs"] == 1
        ctx.mcp_client.vector_writer.upsert.assert_awaited_once()


class TestReindexOnMerge:
    async def test_runs_only_for_develop_branch(self) -> None:
        ctx = _make_context()
        run = await handle_reindex_on_merge(ctx, {"repo_name": "svc", "branch": "develop", "commit_sha": "abc"})
        assert run.status == "success"
        assert run.result["branch"] == "develop"

    async def test_skips_non_develop_branch(self) -> None:
        ctx = _make_context()
        run = await handle_reindex_on_merge(ctx, {"repo_name": "svc", "branch": "main", "commit_sha": "abc"})
        assert run.status == "skipped"


class TestLogAnomalyDigest:
    async def test_computes_deltas_and_stores_baseline(self) -> None:
        ctx = _make_context()
        import asyncpg
        asyncpg.connect = AsyncMock()
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(return_value=None)
        conn.execute = AsyncMock()
        conn.close = AsyncMock()
        asyncpg.connect.return_value = conn

        run = await handle_log_anomaly_digest(ctx)
        assert run.status == "success"
        assert "deltas" in run.result
        assert run.result["slack_ts"] == "12345.6789"
        assert run.result["new_signatures"]

    async def test_skips_duplicate(self) -> None:
        ctx = _make_context()
        await handle_log_anomaly_digest(ctx)
        second = await handle_log_anomaly_digest(ctx)
        assert second.status == "skipped"


class TestConfluenceSync:
    async def test_ingests_pages_and_writes_dedupe_keys(self) -> None:
        ctx = _make_context()
        run = await handle_confluence_sync(ctx)
        assert run.status == "success"
        assert run.result["ingested_pages"] == 1
        ctx.mcp_client.vector_writer.upsert.assert_awaited()


class TestHelpCenterSync:
    async def test_ingests_articles(self) -> None:
        ctx = _make_context()
        run = await handle_help_center_sync(ctx)
        assert run.status == "success"
        assert run.result["ingested_articles"] == 1


class TestCaptureRetention:
    async def test_prunes_old_captures_and_flags_candidates(self) -> None:
        ctx = _make_context()
        ctx.mcp_client.vector_writer.query = AsyncMock(return_value=[
            {"metadata": {"source_id": "item-1"}},
            {"metadata": {"source_id": "item-1"}},
            {"metadata": {"source_id": "item-1"}},
            {"metadata": {"source_id": "item-2"}},
        ])
        run = await handle_capture_retention(ctx)
        assert run.status == "success"
        ctx.mcp_client.vector_writer.delete.assert_awaited_once()
        assert run.result["promotion_candidates"] == [("item-1", 3)]


class TestDocDriftCheck:
    async def test_detects_drift_and_appends(self, tmp_path, monkeypatch) -> None:
        ctx = _make_context()
        async def _fake_pairs(_c):
            return [{
                "id": "pair-1",
                "approved": True,
                "claims": [
                    {"text": "API returns 200", "code_checkable": True, "repo_path": "repo", "expected_pattern": "return 200"},
                ],
            }]
        monkeypatch.setattr("examples.fm_agent.bloom_jobs._read_golden_pairs", _fake_pairs)
        drift_path = tmp_path / "DOC_DRIFT.md"
        async def _fake_append(_c, entries):
            drift_path.write_text("".join(entries))
        monkeypatch.setattr("examples.fm_agent.bloom_jobs._append_doc_drift", _fake_append)

        run = await handle_doc_drift_check(ctx)
        assert run.status == "success"
        assert run.result["drift_count"] == 1
        assert "API returns 200" in drift_path.read_text()

    async def test_skips_duplicate(self) -> None:
        ctx = _make_context()
        first = await dispatch("doc-drift-check", ctx)
        assert first.status == "success"
        second = await dispatch("doc-drift-check", ctx)
        assert second.status == "skipped"


class TestDispatch:
    async def test_routes_known_trigger_to_handler(self) -> None:
        ctx = _make_context()
        run = await dispatch("morning-digest", ctx)
        assert run.status == "success"
        assert run.trigger_id == "morning-digest"

    async def test_rejects_unknown_trigger(self) -> None:
        ctx = _make_context()
        with pytest.raises(ValueError, match="Unknown trigger"):
            await dispatch("unknown-trigger", ctx)

    async def test_deduplicates_dispatch(self) -> None:
        ctx = _make_context()
        await dispatch("morning-digest", ctx)
        second = await dispatch("morning-digest", ctx)
        assert second.status == "skipped"
