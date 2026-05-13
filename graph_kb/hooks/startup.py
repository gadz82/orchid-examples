"""Startup hook for the graph_kb example.

Two responsibilities:

  1. Build an :class:`InMemoryGraphStore`, seed an org-chart corpus
     into it, and inject it into the runtime so the ``graph_rag``
     retrieval strategy can traverse the graph.
  2. Seed a few text chunks into the ``graph_kb`` vector namespace
     so ``fuse_with_vectors: true`` has something to merge with the
     graph context at retrieval time.

Both seedings are best-effort — when the underlying backend rejects
writes the hook logs a warning and continues so the demo still
boots.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Tiny org-chart corpus.  Each entity is a person; edges encode
# ``reports_to`` (manager relation) and ``works_on`` (project
# assignment).
_ENTITIES: list[dict[str, str]] = [
    {"id": "alice", "type": "person", "name": "Alice", "description": "VP Engineering"},
    {"id": "bob", "type": "person", "name": "Bob", "description": "Backend lead"},
    {"id": "carol", "type": "person", "name": "Carol", "description": "Frontend engineer"},
    {"id": "dave", "type": "person", "name": "Dave", "description": "Platform engineer"},
    {"id": "atlas", "type": "project", "name": "Atlas", "description": "RAG redesign"},
    {"id": "nova", "type": "project", "name": "Nova", "description": "Streaming UI"},
]

_EDGES: list[tuple[str, str, str]] = [
    # Reporting relations
    ("bob", "alice", "reports_to"),
    ("carol", "alice", "reports_to"),
    ("dave", "bob", "reports_to"),
    # Project assignments
    ("bob", "atlas", "works_on"),
    ("dave", "atlas", "works_on"),
    ("carol", "nova", "works_on"),
    # Manager relations (inverse for two-hop convenience)
    ("alice", "bob", "manages"),
    ("alice", "carol", "manages"),
    ("bob", "dave", "manages"),
]

_VECTOR_CHUNKS: list[dict[str, str]] = [
    {
        "id": "alice-bio",
        "text": (
            "Alice is the VP of Engineering.  She manages the backend and "
            "frontend teams and oversees the Atlas (RAG redesign) and Nova "
            "(streaming UI) projects."
        ),
    },
    {
        "id": "bob-bio",
        "text": (
            "Bob is the backend lead reporting to Alice.  He works on the "
            "Atlas project and manages the platform team (Dave)."
        ),
    },
    {
        "id": "carol-bio",
        "text": (
            "Carol is a frontend engineer reporting to Alice.  She works on "
            "the Nova streaming UI project."
        ),
    },
    {
        "id": "dave-bio",
        "text": (
            "Dave is a platform engineer reporting to Bob.  He works on the "
            "Atlas RAG redesign project."
        ),
    },
]


async def bootstrap_graph_kb(
    *,
    reader: Any,
    runtime: Any | None = None,
    settings: Any | None = None,
    **_: Any,
) -> None:
    """Seed the graph + vector namespaces and wire the graph store."""
    try:
        from orchid_ai.core.graph_store import OrchidEdge, OrchidEntity
        from orchid_ai.core.repository import Document, OrchidVectorWriter
        from orchid_ai.rag.backends.in_memory_graph import InMemoryGraphStore
        from orchid_ai.rag.scopes import OrchidRAGScope
    except ImportError:
        logger.warning("[GraphKB] orchid_ai imports unavailable — skipping seed")
        return

    # ── 1. Build + seed the graph store ────────────────────────
    graph_store = InMemoryGraphStore()
    seed_scope = OrchidRAGScope(
        tenant_id="__shared__",
        user_id="seed",
        chat_id="",
        agent_id="",
    )

    entities = [
        OrchidEntity(
            id=e["id"],
            type=e["type"],
            name=e["name"],
            properties={"description": e["description"]},
        )
        for e in _ENTITIES
    ]
    await graph_store.upsert_entities(entities, seed_scope)

    edges = [
        OrchidEdge(source_id=src, target_id=dst, relation=rel)
        for (src, dst, rel) in _EDGES
    ]
    await graph_store.upsert_edges(edges, seed_scope)

    # Inject into runtime so build_graph picks it up at agent
    # construction time.  The startup hook fires AFTER the runtime is
    # built but BEFORE build_graph is called from orchid-api lifespan,
    # so this assignment is safe.
    if runtime is not None:
        runtime.graph_store = graph_store
        logger.info("[GraphKB] InMemoryGraphStore wired onto runtime")

    logger.info(
        "[GraphKB] Seeded graph: %d entities + %d edges",
        len(entities),
        len(edges),
    )

    # ── 2. Seed a few vector chunks for fuse_with_vectors ──────
    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[GraphKB] Reader is not a writer — skipping vector seed")
        return

    documents = [
        Document(
            id=chunk["id"],
            page_content=chunk["text"],
            metadata={
                "tenant_id": "__shared__",
                "scope": "tenant",
                "entity_id": chunk["id"].split("-")[0],
                "source": "graph_kb_seed",
            },
        )
        for chunk in _VECTOR_CHUNKS
    ]

    try:
        await reader.upsert(documents, "graph_kb")
        logger.info("[GraphKB] Seeded %d vector chunks into 'graph_kb'", len(documents))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[GraphKB] Vector seed failed: %s", exc)
