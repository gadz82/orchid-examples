"""
Integration test for the recipes example with ChromaDB.

Verifies that the startup hook successfully seeds the recipe corpus
and that retrieval works end-to-end through ChromaRepository.
"""

from __future__ import annotations

import tempfile

import pytest

from orchid_ai.core.repository import OrchidVectorWriter
from orchid_ai.core.scopes import OrchidRAGScope

from examples.recipes.hooks.startup import seed_recipes


class FakeEmbeddings:
    """Minimal embeddings for testing — passes OrchidVectorWriter
    interface by returning identity on the interface check."""

    dimension = 4
    _vec = [0.42] * 4

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec for _ in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return self._vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec


@pytest.fixture
def chroma_repo():
    from orchid_cli.rag.backends.chroma import ChromaRepository

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = ChromaRepository(
            path=tmpdir,
            embeddings=FakeEmbeddings(),
            embedding_dimension=4,
        )
        yield repo


class TestRecipesExample:
    async def test_startup_hook_seeds_correct_number(self, chroma_repo):
        """The startup hook should seed all 8 recipes."""
        await seed_recipes(chroma_repo, None)
        scope = OrchidRAGScope(tenant_id="__shared__")
        results = await chroma_repo.retrieve("chicken", namespace="recipes", k=20, scope=scope)
        assert len(results) == 8, f"Expected 8 recipes, got {len(results)}"

    async def test_seeded_recipe_has_expected_content(self, chroma_repo):
        """The chicken-parmesan recipe should be retrievable by ingredient query."""
        await seed_recipes(chroma_repo, None)
        scope = OrchidRAGScope(tenant_id="__shared__")
        results = await chroma_repo.retrieve("chicken parmesan breaded", namespace="recipes", k=5, scope=scope)
        doc_ids = [r.document.metadata.get("doc_id", "") for r in results]
        assert "chicken-parmesan" in doc_ids, f"chicken-parmesan not found in {doc_ids}"

    async def test_startup_hook_is_idempotent(self, chroma_repo):
        """Calling seed_recipes twice should not raise."""
        await seed_recipes(chroma_repo, None)
        await seed_recipes(chroma_repo, None)
        scope = OrchidRAGScope(tenant_id="__shared__")
        results = await chroma_repo.retrieve("chicken", namespace="recipes", k=20, scope=scope)
        assert len(results) == 8

    async def test_recipe_metadata_is_preserved(self, chroma_repo):
        """Recipe metadata fields should be stored and retrievable."""
        await seed_recipes(chroma_repo, None)
        scope = OrchidRAGScope(tenant_id="__shared__")
        results = await chroma_repo.retrieve("lentil", namespace="recipes", k=10, scope=scope)
        doc_ids = {r.document.metadata.get("doc_id", ""): r.document.metadata for r in results}
        assert "lentil-soup" in doc_ids
        meta = doc_ids["lentil-soup"]
        assert meta.get("cuisine") == "middle_eastern"
        assert meta.get("dietary") == "vegan,gluten_free"
        assert meta.get("prep_time_min") == 45

    async def test_metadata_filter_works_with_recipes(self, chroma_repo):
        """Metadata filter on dietary tags should narrow results."""
        await seed_recipes(chroma_repo, None)
        scope = OrchidRAGScope(tenant_id="__shared__")
        results = await chroma_repo.retrieve(
            "meal",
            namespace="recipes",
            k=10,
            scope=scope,
            metadata_filters={"dietary": "vegan,gluten_free"},
        )
        # At least the vegan recipes should match
        doc_ids = [r.document.metadata.get("doc_id", "") for r in results]
        assert "lentil-soup" in doc_ids
        assert "guacamole" in doc_ids

    async def test_scope_filter_shared_data(self, chroma_repo):
        """Recipes with tenant_id='__shared__' should be visible to any scope."""
        await seed_recipes(chroma_repo, None)
        # Query with a different tenant — should still see __shared__ data
        scope = OrchidRAGScope(tenant_id="some-other-tenant")
        results = await chroma_repo.retrieve("chicken", namespace="recipes", k=5, scope=scope)
        assert len(results) > 0

    async def test_reader_interface_check(self, chroma_repo):
        """ChromaRepository implements OrchidVectorWriter so the startup hook writes."""
        assert isinstance(chroma_repo, OrchidVectorWriter)
