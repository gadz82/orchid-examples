"""RAG-strategies example — built-in retrieval strategies + a custom one.

Demonstrates the :class:`OrchidRetrievalStrategy` extension point by
running four agents that share the same knowledge base but differ on
their ``rag.retrieval.strategy`` setting:

  * ``simple``      — single dense retrieval, fastest baseline.
  * ``multi_query`` — paraphrase fan-out, broader recall.
  * ``hyde``        — hypothetical-document generation, off-distribution
                      queries.
  * ``recency_simple`` (custom) — registered by ``hooks/startup.py``
                                   wraps SimpleRetrieval and sorts
                                   results by recency metadata.

See ``README.md`` for the full walkthrough and a comparison table.
"""
