"""Tests for runtime knowledge capture helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from orchid_ai.core.repository import OrchidDocument
from orchid_ai.rag.scopes import OrchidRAGScope

from examples.fm_agent.hooks.capture import (
    _make_doc_id,
    build_capture_metadata,
    normalize_tool_result,
    redact_and_store,
)


class TestNormalizeToolResult:
    """Cover JSON-to-text normalization."""

    async def test_extracts_title_and_body(self) -> None:
        result = {
            "title": "Incident #42",
            "body": "Service unavailable in us-east-1",
            "url": "https://example.com/incidents/42",
        }
        text = await normalize_tool_result("get_incident", result)

        assert "Incident #42" in text
        assert "Service unavailable" in text
        assert "https://example.com/incidents/42" in text

    async def test_falls_back_to_compact_json(self) -> None:
        result = {"unknown": "shape", "nested": {"value": 1}}
        text = await normalize_tool_result("weird_tool", result)

        assert '"unknown": "shape"' in text

    async def test_handles_non_dict_result(self) -> None:
        text = await normalize_tool_result("echo", "plain text")

        assert text == "plain text"


class TestBuildCaptureMetadata:
    """Cover metadata envelope creation."""

    async def test_metadata_contains_required_fields(self) -> None:
        metadata = await build_capture_metadata(
            source="datadog",
            source_id="log-123",
            source_version="v1",
            url="https://example.com/log/123",
            tool_name="query_logs",
            agent_id="sre-investigator",
        )

        assert metadata["source"] == "datadog"
        assert metadata["source_id"] == "log-123"
        assert metadata["source_version"] == "v1"
        assert metadata["url"] == "https://example.com/log/123"
        assert metadata["tool_name"] == "query_logs"
        assert metadata["agent_id"] == "sre-investigator"
        assert metadata["authority"] == "live"
        assert metadata["scope"] == "chat_agent"
        assert "retrieved_at" in metadata


class TestRedactAndStore:
    """Cover secret redaction, ID generation, and writer calls."""

    @pytest.fixture
    def writer(self):
        return AsyncMock()

    @pytest.fixture
    def metadata(self):
        return {
            "source": "datadog",
            "source_id": "log-123",
            "source_version": "v1",
            "url": "https://example.com/log/123",
            "tool_name": "query_logs",
            "agent_id": "sre-investigator",
            "authority": "live",
            "scope": "chat_agent",
            "retrieved_at": "2024-01-01T00:00:00Z",
        }

    async def test_rejects_when_source_id_missing(self, writer, metadata) -> None:
        metadata["source_id"] = ""
        ok = await redact_and_store("safe text", metadata, writer)
        assert ok is False
        writer.upsert.assert_not_awaited()

    async def test_rejects_when_url_missing(self, writer, metadata) -> None:
        metadata["url"] = ""
        ok = await redact_and_store("safe text", metadata, writer)
        assert ok is False
        writer.upsert.assert_not_awaited()

    async def test_redacts_secrets_before_storing(self, writer, metadata) -> None:
        text = "Deploy key: AKIAIOSFODNN7EXAMPLE and normal text"
        scope = OrchidRAGScope(tenant_id="test")

        ok = await redact_and_store(text, metadata, writer, scope=scope)

        assert ok is True
        writer.upsert.assert_awaited_once()
        args, _kwargs = writer.upsert.call_args
        documents = args[0]
        assert all(isinstance(d, OrchidDocument) for d in documents)
        assert all("AKIAIOSFODNN7EXAMPLE" not in d.page_content for d in documents)
        assert all(d.metadata.get("authority") == "live" for d in documents)
        assert all(d.metadata.get("scope") == "chat_agent" for d in documents)
        assert all("content_hash" in d.metadata for d in documents)

    async def test_doc_ids_are_deterministic(self, writer, metadata) -> None:
        scope = OrchidRAGScope(tenant_id="test")

        await redact_and_store("hello", metadata, writer, scope=scope)
        await redact_and_store("hello", metadata, writer, scope=scope)

        writer.upsert.assert_awaited()
        first_call = writer.upsert.call_args_list[0]
        second_call = writer.upsert.call_args_list[1]
        first_ids = [d.id for d in first_call.args[0]]
        second_ids = [d.id for d in second_call.args[0]]
        assert first_ids == second_ids

    async def test_doc_id_format(self) -> None:
        doc_id = _make_doc_id("datadog", "log-123", 0)
        assert len(doc_id) == 64
        # Deterministic
        assert doc_id == _make_doc_id("datadog", "log-123", 0)
        assert doc_id != _make_doc_id("datadog", "log-123", 1)
