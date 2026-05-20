
"""
Startup hook for the orchid_experts example.

Reads markdown knowledge files from the ``knowledge/`` directory and
seeds them into the corresponding RAG namespaces (orchid-framework,
rag-system, tools-skills, mcp-system, auth-system, bloom-events,
orchid-api-pkg, orchid-cli-pkg, orchid-frontend-pkg, ai-integration).
Runs best-effort — if the vector store is not writable or a file
fails, agents still start.

Wire-up (orchid.yml)::

    startup:
      hook: examples.orchid_experts.hooks.startup.seed_experts_knowledge
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KW_DIR = Path(__file__).resolve().parent.parent / "knowledge"


async def seed_experts_knowledge(reader: Any, settings: Any, **_: Any) -> None:
    """Seed orchid_experts knowledge markdown files into the vector store.

    Each subdirectory under ``knowledge/`` maps to a RAG namespace, e.g.
    ``knowledge/orchid-framework/`` → namespace ``orchid-framework``.
    """
    try:
        from orchid_ai.core.repository import OrchidVectorWriter
        from orchid_ai.documents.pipeline import ingest_document
        from orchid_ai.documents.strategies import RecursiveIngestion
        from orchid_ai.rag.scopes import OrchidRAGScope
    except ImportError:
        logger.warning("[Experts] orchid_ai not available — skipping seed")
        return

    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[Experts] Reader is not a writer — skipping seed")
        return

    shared_scope = OrchidRAGScope(
        tenant_id="__shared__",
        user_id="seed",
        chat_id="",
        agent_id="",
    )
    strategy = RecursiveIngestion()
    total_seeded = 0

    for ns_dir in sorted(_KW_DIR.iterdir()):
        if not ns_dir.is_dir():
            continue

        namespace = ns_dir.name
        for md_file in sorted(ns_dir.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                await ingest_document(
                    file_bytes=content.encode("utf-8"),
                    filename=md_file.name,
                    scope=shared_scope,
                    namespace=namespace,
                    writer=reader,
                    ingestion=strategy,
                    pre_extracted_text=content,
                )
                total_seeded += 1
            except Exception as exc:
                logger.warning(
                    "[Experts] Failed to seed %s/%s: %s",
                    namespace,
                    md_file.name,
                    exc,
                )

    logger.info(
        "[Experts] Seeded %d files across %d namespaces",
        total_seeded,
        sum(1 for d in _KW_DIR.iterdir() if d.is_dir()),
    )
