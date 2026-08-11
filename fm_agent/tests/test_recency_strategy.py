"""Tests for the recency-hybrid retrieval strategy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from orchid_ai.core.repository import OrchidDocument, OrchidSearchResult

from examples.fm_agent.recency_strategy import RecencyHybridRetrieval


class TestRecencyHybridRetrieval:
    """Cover oversampling, recency re-ranking, and fallback behavior."""

    @pytest.fixture
    def strategy(self):
        return RecencyHybridRetrieval()

    async def test_oversamples_before_reranking(self, strategy) -> None:
        reader = AsyncMock()
        scope = AsyncMock()

        with patch("examples.fm_agent.recency_strategy.HybridRetrieval") as mock_cls:
            hybrid_instance = AsyncMock()
            hybrid_instance.retrieve = AsyncMock(return_value=[])
            mock_cls.return_value = hybrid_instance

            await strategy.retrieve(
                query="what is the retry policy",
                namespace="runbooks",
                scope=scope,
                k=5,
                reader=reader,
            )

            hybrid_instance.retrieve.assert_awaited_once()
            assert hybrid_instance.retrieve.await_args.kwargs["k"] == 15

    async def test_newer_documents_rank_higher(self) -> None:
        from examples.fm_agent.recency_strategy import RecencyHybridConfig

        strategy = RecencyHybridRetrieval(RecencyHybridConfig(recency_weight=0.6))
        reader = AsyncMock()
        scope = AsyncMock()

        now = datetime.now(UTC)
        old = OrchidDocument(
            page_content="old doc",
            metadata={"updated_at": (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")},
        )
        recent = OrchidDocument(
            page_content="recent doc",
            metadata={"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
        )

        with patch("examples.fm_agent.recency_strategy.HybridRetrieval") as mock_cls:
            hybrid_instance = AsyncMock()
            # Return in reverse semantic order so re-ranking must fix it
            hybrid_instance.retrieve = AsyncMock(return_value=[
                OrchidSearchResult(document=old, score=0.75),
                OrchidSearchResult(document=recent, score=0.73),
            ])
            mock_cls.return_value = hybrid_instance

            results = await strategy.retrieve(
                query="retry policy",
                namespace="runbooks",
                scope=scope,
                k=2,
                reader=reader,
            )

            assert len(results) == 2
            assert results[0].document.page_content == "recent doc"
            assert results[1].document.page_content == "old doc"

    async def test_documents_without_updated_at_keep_score(self, strategy) -> None:
        reader = AsyncMock()
        scope = AsyncMock()

        doc = OrchidDocument(
            page_content="no date",
            metadata={"repo": "test"},
        )

        with patch("examples.fm_agent.recency_strategy.HybridRetrieval") as mock_cls:
            hybrid_instance = AsyncMock()
            hybrid_instance.retrieve = AsyncMock(return_value=[
                OrchidSearchResult(document=doc, score=0.5),
            ])
            mock_cls.return_value = hybrid_instance

            results = await strategy.retrieve(
                query="no date doc",
                namespace="runbooks",
                scope=scope,
                k=1,
                reader=reader,
            )

            assert len(results) == 1
            assert results[0].score == 0.5
