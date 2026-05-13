"""
Startup hook for the rag-strategies example.

Two responsibilities:

  1. Register the custom :class:`RecencySimpleRetrieval` strategy so
     ``rag.retrieval.strategy: recency_simple`` resolves through the
     registry.
  2. Seed a small "release notes" corpus with ``published_at``
     metadata into the ``release_notes`` namespace so the recency
     strategy has time-stamped material to re-rank.

Wire-up (orchid.yml)::

    startup:
      hook: examples.rag-strategies.hooks.startup.bootstrap_rag_strategies
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


# A tiny dated corpus exercising the recency strategy.
_RELEASE_NOTES: list[dict[str, Any]] = [
    {
        "id": "rel-2026-04-12",
        "published_at": "2026-04-12T00:00:00",
        "content": (
            "Release 5.4 — Streaming SSE events now include mini-agent "
            "lifecycle markers (decomposed, started, finished, aggregated)."
        ),
    },
    {
        "id": "rel-2026-02-01",
        "published_at": "2026-02-01T00:00:00",
        "content": (
            "Release 5.2 — Phase A parallel tool dispatch ships behind "
            "the per-agent ``parallel_tools: true`` flag.  Read-only MCP "
            "tools annotated ``readOnlyHint`` are gathered via "
            "asyncio.gather within a single agentic round."
        ),
    },
    {
        "id": "rel-2025-11-08",
        "published_at": "2025-11-08T00:00:00",
        "content": (
            "Release 5.0 — Hierarchical RAG scopes (root → tenant → user "
            "→ chat → agent), pluggable retrieval strategies, and the "
            "OrchidQueryTransformer ABC arrive in this milestone."
        ),
    },
    {
        "id": "rel-2025-08-22",
        "published_at": "2025-08-22T00:00:00",
        "content": (
            "Release 4.6 — MCP OAuth (RFC 9728 / RFC 8414 / RFC 7591 DCR) "
            "is now supported via the ``oauth`` auth mode.  Tokens land "
            "in OrchidMCPTokenStore; client registrations in "
            "OrchidMCPClientRegistrationStore."
        ),
    },
]


async def bootstrap_rag_strategies(reader: Any, settings: Any, **_: Any) -> None:
    """Register the custom strategy and seed the release-notes corpus."""
    # 1) Strategy registration ───────────────────────────────
    from orchid_ai.rag.strategies import register_retrieval_strategy

    recency_module = importlib.import_module(
        "examples.rag-strategies.strategies.recency",
    )
    register_retrieval_strategy("recency_simple", recency_module.RecencySimpleRetrieval)
    logger.info("[RAGStrategies] Registered custom strategy: recency_simple")

    # 2) RAG seed (best-effort) ──────────────────────────────
    try:
        from orchid_ai.core.repository import Document, OrchidVectorWriter
    except ImportError:
        logger.warning("[RAGStrategies] orchid_ai not available — skipping seed")
        return

    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[RAGStrategies] Reader is not a writer — skipping seed")
        return

    documents = [
        Document(
            id=note["id"],
            page_content=note["content"],
            metadata={
                "tenant_id": "__shared__",
                "scope": "tenant",
                "published_at": note["published_at"],
                "source": "release_notes",
            },
        )
        for note in _RELEASE_NOTES
    ]

    try:
        await reader.upsert(documents, "release_notes")
        logger.info("[RAGStrategies] Seeded %d release notes", len(documents))
    except Exception as exc:
        logger.warning("[RAGStrategies] RAG seed failed: %s", exc)
