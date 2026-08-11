"""Tests for the evaluation harness."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import yaml

from examples.fm_agent.evals.generate import _extract_claims, _fetch_confluence_grounding, _verify_claims
from examples.fm_agent.evals.run import _build_report, _dry_run_result, _judge_faithfulness, run_evals


class TestReportBuilder:
    """Cover RESULTS.md aggregation and formatting."""

    def test_report_summary_counts(self) -> None:
        results = [
            {
                "id": "q1", "question": "What is X?", "agent_correct": True,
                "source_path_found": True, "faithful": True, "faithfulness_score": 0.9,
                "error": "",
            },
            {
                "id": "q2", "question": "What is Y?", "agent_correct": False,
                "source_path_found": False, "faithful": False, "faithfulness_score": 0.2,
                "error": "boom",
            },
        ]
        agg = {
            "total": 2, "correct_agent": 1, "source_path_found": 1,
            "faithful": 1, "avg_faithfulness_score": 0.55,
            "run_at": "2024-01-01T00:00:00Z", "seed": 42, "api_url": "http://test",
        }
        report = _build_report(results, agg)

        assert "Total pairs | 2" in report
        assert "Correct agent routed | 1/2" in report
        assert "Source path found | 1/2" in report
        assert "Faithful answers | 1/2" in report
        assert "boom" in report

    def test_report_empty_results(self) -> None:
        report = _build_report([], {
            "total": 0, "correct_agent": 0, "source_path_found": 0,
            "faithful": 0, "avg_faithfulness_score": 0.0,
            "run_at": "2024-01-01T00:00:00Z", "seed": 42, "api_url": "http://test",
        })

        assert "Total pairs | 0" in report


class TestGoldenFileLoader:
    """Cover loading and fallback behavior."""

    async def test_dry_run_skips_api(self, tmp_path) -> None:
        golden = tmp_path / "golden.yaml"
        golden.write_text(yaml.safe_dump({"entries": [{"id": "q1", "question": "Q?", "expected_answer": "A", "agent": "x", "status": "draft"}]}))
        results = tmp_path / "RESULTS.md"

        result_path = await run_evals(
            golden_path=str(golden),
            results_path=str(results),
            dry_run=True,
        )

        assert result_path == str(results)
        assert results.exists()
        assert "Mode:** dry-run" in results.read_text()

    async def test_local_test_uses_mock_client(self, tmp_path) -> None:
        golden = tmp_path / "golden.yaml"
        golden.write_text(yaml.safe_dump({"entries": [{"id": "q1", "question": "Q?", "expected_answer": "A", "agent": "notification-expert", "status": "draft"}]}))
        results = tmp_path / "RESULTS.md"

        result_path = await run_evals(
            golden_path=str(golden),
            results_path=str(results),
            local_test=True,
        )

        assert result_path == str(results)
        text = results.read_text()
        assert "Mode:** local-test" in text
        assert "✓" in text

    async def test_dry_run_result_shape(self) -> None:
        result = _dry_run_result({"id": "q1", "question": "Q?"})
        assert result["response"] == "[dry-run]"
        assert result["error"] == ""


class TestJudgeFaithfulness:
    """Cover the judge prompt and parsing."""

    async def test_judge_returns_zero_on_llm_failure(self) -> None:
        with patch("litellm.acompletion", AsyncMock(side_effect=RuntimeError("LLM down"))):
            score = await _judge_faithfulness("Q", "A", "B")

        assert score == 0.0

    async def test_judge_parses_json_score(self) -> None:
        with patch("litellm.acompletion", AsyncMock(return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"score": 0.8, "reason": "good"}'))]
        ))):
            score = await _judge_faithfulness("Q", "A", "B")

        assert score == 0.8


class TestClaimExtraction:
    """Cover factual claim parsing and verification."""

    def test_extracts_endpoints_versions_and_constants(self) -> None:
        answer = "Call POST /notifications/v2. The MAILER_QUEUE is used in v1.2.3."
        claims = _extract_claims(answer)

        tokens = {t for claim in claims for t in claim["tokens"]}
        assert "/notifications/v2" in tokens
        assert "MAILER_QUEUE" in tokens
        assert "v1.2.3" in tokens

    def test_verify_confirmed_when_all_tokens_found(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "config.yml").write_text("MAILER_QUEUE: queue-name")

        claims = [{"sentence": "Use MAILER_QUEUE", "tokens": ["MAILER_QUEUE"]}]
        verified = _verify_claims(claims, [str(repo)])

        assert verified["verdict"] == "confirmed"
        assert "MAILER_QUEUE" not in verified["missing"]
        assert verified["verdict"] != "unverified"

    def test_verify_unverified_when_no_tokens_found(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "config.yml").write_text("other: value")

        claims = [{"sentence": "Use MAILER_QUEUE", "tokens": ["MAILER_QUEUE"]}]
        verified = _verify_claims(claims, [str(repo)])

        assert verified["verdict"] == "unverified"
        assert "MAILER_QUEUE" in verified["missing"]


class TestConfluenceGrounding:
    """Cover Confluence grounding credential handling and allowlist."""

    async def test_skips_when_no_config(self, tmp_path) -> None:
        writer = AsyncMock()
        count = await _fetch_confluence_grounding(writer, str(tmp_path / "missing.yaml"))
        assert count == 0
        writer.upsert.assert_not_awaited()

    async def test_skips_when_no_credentials(self, tmp_path, monkeypatch) -> None:
        config = tmp_path / "agents.yaml"
        config.write_text(yaml.safe_dump({"mcp_servers": [{"name": "atlassian-rovo", "tools": [{"name": "getConfluencePage", "inject_to_rag": True}]}]}))
        monkeypatch.setenv("ATLASSIAN_DOMAIN", "")
        monkeypatch.setenv("ATLASSIAN_TOKEN", "")
        monkeypatch.setenv("ATLASSIAN_EMAIL", "")
        monkeypatch.setenv("ATLASSIAN_API_TOKEN", "")

        writer = AsyncMock()
        count = await _fetch_confluence_grounding(writer, str(config))

        assert count == 0
        writer.upsert.assert_not_awaited()

    async def test_skips_when_tools_not_allowlisted(self, tmp_path, monkeypatch) -> None:
        config = tmp_path / "agents.yaml"
        config.write_text(yaml.safe_dump({"mcp_servers": [{"name": "atlassian-rovo", "tools": [{"name": "other", "inject_to_rag": True}]}]}))
        monkeypatch.setenv("ATLASSIAN_DOMAIN", "example.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_TOKEN", "token")

        writer = AsyncMock()
        count = await _fetch_confluence_grounding(writer, str(config))

        assert count == 0
        writer.upsert.assert_not_awaited()

    async def test_fetches_and_upserts_pages(self, tmp_path, monkeypatch) -> None:
        config = tmp_path / "agents.yaml"
        config.write_text(yaml.safe_dump({"mcp_servers": [{"name": "atlassian-rovo", "tools": [
            {"name": "getConfluenceSpaces", "inject_to_rag": True},
            {"name": "getPagesInConfluenceSpace", "inject_to_rag": True},
            {"name": "getConfluencePage", "inject_to_rag": True},
        ]}]}))
        monkeypatch.setenv("ATLASSIAN_DOMAIN", "example.atlassian.net")
        monkeypatch.setenv("ATLASSIAN_TOKEN", "token")

        writer = AsyncMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            client.get = AsyncMock(side_effect=[
                MagicMock(raise_for_status=lambda: None, json=lambda: {"results": [{"key": "HYD"}]}),
                MagicMock(raise_for_status=lambda: None, json=lambda: {"results": [{"id": "123"}]}),
                MagicMock(raise_for_status=lambda: None, json=lambda: {"title": "Page", "body": {"storage": {"value": "<p>Hello</p>"}}}),
            ])
            mock_client_cls.return_value = client

            count = await _fetch_confluence_grounding(writer, str(config))

        assert count > 0
        writer.upsert.assert_awaited_once()
