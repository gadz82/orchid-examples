"""
Custom retrieval strategy: ``recency_simple``.

Wraps :class:`SimpleRetrieval`-style dense retrieval and re-sorts the
top-``k`` results by a ``published_at`` metadata field (descending),
breaking ties by the original score.  Useful when the knowledge base
contains time-sensitive material — release notes, news, customer
emails — and the integrator wants "most recent relevant" rather than
"most semantically similar".

Demonstrates the :class:`OrchidRetrievalStrategy` extension contract:

  1. Subclass :class:`OrchidRetrievalStrategy`.
  2. Implement :meth:`retrieve` matching the ABC signature.
  3. Optionally override :meth:`from_config` to consume YAML knobs —
     here, ``recency_field`` and ``recency_weight``.
  4. Register via :func:`register_retrieval_strategy` in a startup
     hook so the registry is populated before any agent boots.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from orchid_ai.core.doc_store import OrchidDocStore
from orchid_ai.core.graph_store import OrchidGraphStore
from orchid_ai.core.repository import OrchidSearchResult, OrchidVectorReader
from orchid_ai.core.retrieval import OrchidQueryTransformer, OrchidRetrievalStrategy
from orchid_ai.core.scopes import OrchidRAGScope

logger = logging.getLogger(__name__)


class RecencySimpleRetrieval(OrchidRetrievalStrategy):
    """Single dense retrieval re-sorted by a recency metadata field."""

    def __init__(
        self,
        *,
        recency_field: str = "published_at",
        recency_weight: float = 1.0,
    ) -> None:
        self._recency_field = recency_field
        # ``recency_weight`` blends the recency signal into the score —
        # 0.0 means "tie-break only", 1.0 means "ignore semantic score
        # entirely".  Anything in between is a weighted blend.
        if not 0.0 <= recency_weight <= 1.0:
            raise ValueError(f"recency_weight must be in [0, 1]; got {recency_weight}")
        self._recency_weight = recency_weight

    @classmethod
    def from_config(cls, config: Any) -> "RecencySimpleRetrieval":
        """Read strategy-specific knobs from the agent's retrieval config.

        The framework attaches custom knobs via free-form YAML — we
        look up two optional attributes on ``config`` and fall back to
        the constructor defaults when they're missing.  Pydantic's
        ``extra="forbid"`` on ``OrchidRetrievalConfig`` means custom
        knobs typically land on a sibling config the integrator owns
        (or via ``model_config``-tweaked subclass) — in this example
        the YAML keeps the strategy on the defaults so we just use
        constructor defaults.
        """
        if config is None:
            return cls()
        recency_field = getattr(config, "recency_field", "published_at")
        recency_weight = getattr(config, "recency_weight", 1.0)
        return cls(
            recency_field=recency_field,
            recency_weight=recency_weight,
        )

    async def retrieve(
        self,
        *,
        query: str,
        namespace: str,
        scope: OrchidRAGScope,
        k: int,
        reader: OrchidVectorReader,
        chat_model: Any | None = None,
        graph_store: OrchidGraphStore | None = None,
        doc_store: OrchidDocStore | None = None,
        transformers: list[OrchidQueryTransformer] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[OrchidSearchResult]:
        # Pull a deeper-than-k slice so the recency re-sort has
        # candidates to compete on.  Cap at ``2 * k`` to keep cost
        # bounded — the default reader paginates internally.
        oversample_k = max(k * 2, k)
        results = await reader.retrieve(
            query=query,
            namespace=namespace,
            k=oversample_k,
            scope=scope,
            metadata_filters=metadata_filters,
        )

        # Re-rank by ``recency_field`` (descending).  Documents
        # missing the field land at the bottom — they cannot beat
        # any timestamped peer.
        def _key(r: OrchidSearchResult) -> tuple:
            ts = self._extract_timestamp(r.document.metadata.get(self._recency_field))
            recency_score = ts if ts is not None else 0
            blended = (
                (1.0 - self._recency_weight) * r.score
                + self._recency_weight * recency_score
            )
            return blended, ts or 0

        results.sort(key=_key, reverse=True)
        return results[:k]

    @staticmethod
    def _extract_timestamp(value: Any) -> float | None:
        """Coerce ``value`` to a Unix timestamp, returning ``None`` on miss.

        Accepts ISO-8601 strings, ``datetime``, ``int`` / ``float``
        (already a timestamp).  Anything else logs a debug line and
        returns ``None`` so the caller can demote that document.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            return value.timestamp()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value).timestamp()
            except ValueError:
                logger.debug("[RecencySimpleRetrieval] non-ISO timestamp: %r", value)
                return None
        logger.debug("[RecencySimpleRetrieval] unsupported timestamp type: %r", type(value).__name__)
        return None
