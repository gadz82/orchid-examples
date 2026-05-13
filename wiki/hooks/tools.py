"""Built-in tools for the wiki example.

The ``lookup_glossary`` tool is wired in ``agents.yaml`` with a
per-tool RAG override (ADR-024) — its results land in a different
namespace and use a different ingestion strategy than the agent's
own RAG block.
"""

from __future__ import annotations

# A tiny in-memory glossary so the demo runs without external services.
_GLOSSARY: dict[str, str] = {
    "rag": (
        "RAG (Retrieval-Augmented Generation) is the pattern of fetching "
        "context-relevant documents from a vector store and feeding them "
        "to an LLM as additional context before generation.  In Orchid, "
        "RAG is configured via the agent's ``rag:`` block — namespace, "
        "ingestion strategy, retrieval strategy, k, and metadata filters."
    ),
    "hybrid": (
        "Hybrid retrieval combines dense (semantic-vector) similarity "
        "with sparse (BM25 or SPLADE) lexical matching.  Orchid fuses "
        "the two ranked lists via reciprocal-rank-fusion (``rrf``) by "
        "default; ``linear`` fusion is also supported via "
        "``hybrid.fusion: linear`` + ``sparse_weight``."
    ),
    "headered": (
        "The ``headered`` ingestion strategy wraps recursive splitting "
        "with a contextual-header post-processor: each chunk is "
        "prepended with the source filename and the nearest preceding "
        "markdown heading so retrieval can match by section title."
    ),
}


async def lookup_glossary(term: str, **_: object) -> dict[str, object]:
    """Look up a term in the demo glossary.

    Returns a dict so the result is JSON-serialised by the dynamic
    injection path before the configured ingestion strategy splits
    it into chunks.
    """
    key = term.strip().lower()
    if key not in _GLOSSARY:
        return {"error": f"No glossary entry for {term!r}"}
    return {"term": key, "definition": _GLOSSARY[key]}
