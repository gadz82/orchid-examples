"""Startup hook for the wiki example.

Seeds two corpora: long-form documentation pages (ingested with the
``headered`` strategy via the documents pipeline) and tight FAQ
snippets (default ``recursive`` strategy).  Best-effort — if the
backend doesn't support writing, the hook quietly returns.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


_DOC_PAGES: list[dict[str, str]] = [
    {
        "id": "rag-config-page",
        "filename": "configuration/rag.md",
        "content": (
            "# Configuration > RAG\n\n"
            "Each agent declares its retrieval pipeline under ``rag:``.\n"
            "The most important fields are ``namespace`` (the Qdrant\n"
            "collection), ``k`` (top-k results), ``ingestion`` (how\n"
            "uploads are chunked), and ``retrieval`` (how the query is\n"
            "turned into ranked results).\n\n"
            "## Hybrid retrieval\n\n"
            "Set ``retrieval.strategy: hybrid`` to fuse dense vector\n"
            "search with BM25.  The ``hybrid.fusion`` field picks the\n"
            "fusion function: ``rrf`` (default, parameter-free) or\n"
            "``linear`` with a configurable ``sparse_weight``.\n\n"
            "## Per-tool overrides\n\n"
            "Tools listed under ``tools:`` (built-in) or under an MCP\n"
            "server may carry their own ``rag:`` block.  When set,\n"
            "the tool's results use that override instead of the\n"
            "agent's RAG block — useful for caching reference data\n"
            "into a different namespace or chunking layout."
        ),
    },
    {
        "id": "ingestion-page",
        "filename": "configuration/ingestion.md",
        "content": (
            "# Configuration > Ingestion\n\n"
            "The ``ingestion.strategy`` field selects the chunker.\n"
            "Stage 1 ships ``recursive``; Stage 2 adds ``semantic``,\n"
            "``hierarchical``, ``headered``.\n\n"
            "## Recursive\n\n"
            "Standard character-based splitting with overlap.  Good\n"
            "default for prose-heavy documents under 50 pages.\n\n"
            "## Semantic\n\n"
            "Detects topic boundaries by measuring embedding\n"
            "similarity between adjacent paragraphs.  Best for\n"
            "narrative content where fixed-size splits cut sentences\n"
            "in half.\n\n"
            "## Hierarchical\n\n"
            "Two-tier layout: the chunker writes large parent chunks\n"
            "to an ``OrchidDocStore`` and emits small child chunks\n"
            "for embedding.  Retrieval lifts the parent payload at\n"
            "synthesis time so the LLM sees the full context.\n\n"
            "## Headered\n\n"
            "Wraps ``recursive`` with the\n"
            "``contextual_headers`` post-processor.  Each chunk is\n"
            "prepended with its source filename and the nearest\n"
            "preceding markdown heading."
        ),
    },
]

_FAQ_SNIPPETS: list[dict[str, str]] = [
    {
        "id": "faq-rag-disabled",
        "content": (
            "Q: How do I disable RAG for a single agent?\n"
            "A: Set ``rag.enabled: false`` on that agent.  No retrieval\n"
            "step runs and ``rag_data`` is empty when the agent\n"
            "summarises."
        ),
    },
    {
        "id": "faq-cache-ttl",
        "content": (
            "Q: How do I tune the dynamic-injection cache?\n"
            "A: Set ``rag_ttl`` in seconds at the defaults, agent, or\n"
            "tool level.  ``0`` disables caching (every call hits the\n"
            "tool fresh)."
        ),
    },
    {
        "id": "faq-namespace-collisions",
        "content": (
            "Q: Two agents share a namespace — is that safe?\n"
            "A: Yes.  Hierarchical scoping isolates writes by\n"
            "tenant / user / chat; the namespace is just a Qdrant\n"
            "collection.  Multiple agents can read each other's chat-\n"
            "scoped data within the same chat."
        ),
    },
]


async def bootstrap_wiki(reader: Any, settings: Any, **_: Any) -> None:
    """Seed the wiki example's two namespaces."""
    try:
        from orchid_ai.core.repository import OrchidVectorWriter
        from orchid_ai.documents.pipeline import ingest_document
        from orchid_ai.documents.strategies import (
            HeaderedIngestion,
            RecursiveIngestion,
        )
        from orchid_ai.rag.scopes import OrchidRAGScope
    except ImportError:
        logger.warning("[Wiki] orchid_ai imports unavailable — skipping seed")
        return

    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[Wiki] Reader is not a writer — skipping seed")
        return

    shared_scope = OrchidRAGScope(
        tenant_id="__shared__",
        user_id="seed",
        chat_id="",
        agent_id="",
    )

    # ── 1. Long-form docs via ``headered`` strategy ────────────
    docs_strategy = HeaderedIngestion()
    for page in _DOC_PAGES:
        try:
            await ingest_document(
                file_bytes=page["content"].encode("utf-8"),
                filename=page["filename"],
                scope=shared_scope,
                namespace="wiki_docs",
                writer=reader,
                ingestion=docs_strategy,
                pre_extracted_text=page["content"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Wiki] Failed to seed docs page %s: %s", page["id"], exc)

    # ── 2. FAQ snippets via ``recursive`` strategy ─────────────
    faq_strategy = RecursiveIngestion()
    for snippet in _FAQ_SNIPPETS:
        try:
            await ingest_document(
                file_bytes=snippet["content"].encode("utf-8"),
                filename=f"{snippet['id']}.txt",
                scope=shared_scope,
                namespace="wiki_faq",
                writer=reader,
                ingestion=faq_strategy,
                pre_extracted_text=snippet["content"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Wiki] Failed to seed FAQ %s: %s", snippet["id"], exc)

    logger.info(
        "[Wiki] Seeded %d doc pages + %d FAQ snippets",
        len(_DOC_PAGES),
        len(_FAQ_SNIPPETS),
    )
