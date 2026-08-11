"""Runtime knowledge capture — normalize and persist live MCP tool results.

These helpers are used by agents to turn raw tool JSON into chunked,
searchable memory with deterministic IDs, secret redaction, and
metadata that marks the content as ``authority=live``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from orchid_ai.core.repository import OrchidDocument, OrchidVectorWriter
from orchid_ai.documents.strategies import HeaderedIngestion
from orchid_ai.rag.scopes import OrchidRAGScope

from examples.fm_agent.indexer.secrets import SecretScanner

logger = logging.getLogger(__name__)

CAPTURE_NAMESPACE = "live-memory"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_doc_id(source: str, source_id: str, ordinal: int) -> str:
    return hashlib.sha256(f"{source}|{source_id}|{ordinal}".encode()).hexdigest()


async def normalize_tool_result(tool_name: str, result: dict[str, Any]) -> str:
    """Normalize a raw tool result dict into plain text for indexing.

    Extracts a title, body, and a few well-known key fields.  Falls back
    to a compact JSON dump when the structure is not recognized.
    """
    if not isinstance(result, dict):
        return str(result)

    body = result.get("body") or result.get("content") or result.get("text") or result.get("description") or ""
    if not body and "snippet" in result:
        body = result["snippet"]
    title = result.get("title") or result.get("name") or result.get("subject") or ""

    if body:
        lines = [f"# {title}"] if title else []
        lines.append(str(body))
        for key in ("url", "link", "html_url", "web_url", "self"):
            if result.get(key):
                lines.append(f"{key}: {result[key]}")
        return "\n\n".join(lines)

    # Fallback: compact JSON
    try:
        return json.dumps(result, ensure_ascii=False, indent=2)
    except TypeError:
        return str(result)


async def build_capture_metadata(
    source: str,
    source_id: str,
    source_version: str,
    url: str,
    tool_name: str,
    agent_id: str,
) -> dict[str, Any]:
    """Build the metadata envelope for a captured live result."""
    return {
        "source": source,
        "source_id": source_id,
        "source_version": source_version,
        "url": url,
        "retrieved_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool_name": tool_name,
        "agent_id": agent_id,
        "authority": "live",
        "scope": "chat_agent",
    }


async def redact_and_store(
    content: str,
    metadata: dict[str, Any],
    writer: OrchidVectorWriter,
    namespace: str = CAPTURE_NAMESPACE,
    scope: OrchidRAGScope | None = None,
) -> bool:
    """Redact secrets and store normalized live content into the vector index.

    Returns ``True`` if at least one chunk was written.
    """
    source_id = metadata.get("source_id", "")
    url = metadata.get("url", "")
    if not source_id or not url:
        logger.warning("Rejecting live capture: missing source_id or url")
        return False

    scanner = SecretScanner()
    scan_result = scanner.scan(content)
    text = scan_result.cleaned_text

    content_hash = _content_hash(text)
    metadata = dict(metadata)
    metadata["content_hash"] = content_hash

    strategy = HeaderedIngestion()
    chunks = await strategy.ingest(text=text, filename=metadata.get("source_id", "capture"), scope=scope)

    if not chunks:
        logger.warning("No chunks produced for live capture %s", source_id)
        return False

    source = metadata.get("source", "live")
    documents: list[OrchidDocument] = []
    for i, chunk in enumerate(chunks):
        doc_id = _make_doc_id(source, source_id, i)
        chunk_metadata = dict(chunk.metadata)
        chunk_metadata.update(metadata)
        documents.append(OrchidDocument(
            id=doc_id,
            page_content=chunk.text,
            metadata=chunk_metadata,
        ))

    await writer.upsert(documents, namespace)
    logger.info("Captured live result: %s/%s → %d chunks", source, source_id, len(documents))
    return True
