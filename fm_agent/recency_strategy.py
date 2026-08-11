"""Recency-hybrid retrieval strategy.

Hybrid retrieval (dense + sparse via BM25, RRF fusion) re-ranked by
``updated_at`` metadata so the newest documents rank highest.  Used by
the ``runbooks`` namespace — during incidents the newest postmortem beats
the semantically-closest stale one.

Modeled on the ``hybrid`` built-in; adds a post-retrieval recency pass.
Registered at startup via ``hooks/startup.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from orchid_ai.core.repository import OrchidSearchResult, OrchidVectorReader
from orchid_ai.core.retrieval import OrchidRetrievalStrategy
from orchid_ai.rag.strategies.hybrid import HybridRetrieval


@dataclass
class RecencyHybridConfig:
    """Knobs for the recency_hybrid strategy, read from YAML."""

    recency_weight: float = 0.3
    max_age_days: float = 365.0
    fallback_strategy: str = "hybrid"


class RecencyHybridRetrieval(OrchidRetrievalStrategy):
    """Hybrid retrieval re-ranked by ``updated_at`` metadata.

    Retrieves ``k * 3`` results via hybrid fusion, then re-ranks by a
    decay-weighted recency score so fresher documents surface first.
    Falls back to plain ``hybrid`` when no results carry ``updated_at``.
    """

    def __init__(self, config: RecencyHybridConfig | None = None) -> None:
        self._config = config or RecencyHybridConfig()

    @classmethod
    def from_config(cls, config: Any) -> RecencyHybridRetrieval:
        """Build from YAML retrieval.recency block."""
        recency_cfg = getattr(config, "recency", None)
        if recency_cfg is not None and isinstance(recency_cfg, dict):
            return cls(RecencyHybridConfig(
                recency_weight=float(recency_cfg.get("recency_weight", 0.3)),
                max_age_days=float(recency_cfg.get("max_age_days", 365)),
                fallback_strategy=str(recency_cfg.get("fallback_strategy", "hybrid")),
            ))
        return cls()

    async def retrieve(
        self,
        *,
        query: str,
        namespace: str,
        scope: Any,
        k: int,
        reader: OrchidVectorReader,
        chat_model: Any = None,
        graph_store: Any = None,
        doc_store: Any = None,
        transformers: list[Any] | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[OrchidSearchResult]:
        """Run hybrid retrieval then re-rank by recency."""
        # Oversample: fetch more results than needed so we have room to re-rank
        oversample_k = max(k * 3, 15)

        hybrid = HybridRetrieval()
        raw_results = await hybrid.retrieve(
            query=query,
            namespace=namespace,
            scope=scope,
            k=oversample_k,
            reader=reader,
            chat_model=chat_model,
            graph_store=graph_store,
            doc_store=doc_store,
            transformers=transformers,
            metadata_filters=metadata_filters,
        )

        if not raw_results:
            return []

        # Re-rank: blend semantic score with recency decay
        now = _utcnow()
        re_ranked = []
        for result in raw_results:
            _, _, score = self._re_score(result, now)
            re_ranked.append((score, result))

        re_ranked.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in re_ranked[:k]]

    def _re_score(
        self, result: OrchidSearchResult, now: datetime,
    ) -> tuple[float, float, float]:
        """Blend semantic score with recency decay.

        Returns (semantic_score, recency_score, blended_score).
        """
        sem_score = result.score
        updated_at = _parse_updated_at(result.document.metadata.get("updated_at"))
        if updated_at is None:
            return sem_score, 0.0, sem_score

        age_days = (now - updated_at).total_seconds() / 86400.0
        max_age = self._config.max_age_days
        if age_days <= 0:
            recency_score = 1.0
        elif age_days >= max_age:
            recency_score = 0.0
        else:
            recency_score = 1.0 - (age_days / max_age)

        w = self._config.recency_weight
        blended = sem_score * (1.0 - w) + recency_score * w
        return sem_score, recency_score, blended


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _parse_updated_at(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if not isinstance(val, str):
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            parsed = datetime.strptime(val, fmt)  # noqa: DTZ007
            parsed = parsed.replace(tzinfo=parsed.tzinfo or UTC)
            return parsed
        except (ValueError, OverflowError):
            continue
    return None
