"""Self-tests for the in-memory vector store."""

from __future__ import annotations

import pytest
from examples._e2e_shared.fixtures.mock_vector import (
    InMemoryVectorStore,
    OrchidDocument,
    OrchidRAGScope,
    OrchidVectorReader,
    OrchidVectorWriter,
    seed_documents,
)


@pytest.fixture
def store() -> InMemoryVectorStore:
    return InMemoryVectorStore()


async def test_reader_returns_seeded_docs(store: InMemoryVectorStore) -> None:
    seed_documents(
        store,
        "kb",
        [
            OrchidDocument(page_content="Python is great", id="doc-1"),
            OrchidDocument(page_content="JavaScript is okay", id="doc-2"),
        ],
    )
    reader = store.reader()
    results = await reader.retrieve("python", namespace="kb", k=2)
    assert len(results) == 1
    assert results[0].document.id == "doc-1"


async def test_writer_indexes_then_reader_finds(store: InMemoryVectorStore) -> None:
    writer = store.writer()
    await writer.index(
        [OrchidDocument(page_content="Orchid framework", id="doc-3")],
        namespace="docs",
    )
    results = await store.reader().retrieve("orchid", namespace="docs", k=1)
    assert len(results) == 1
    assert results[0].document.id == "doc-3"


async def test_delete_removes_doc(store: InMemoryVectorStore) -> None:
    writer = store.writer()
    await writer.index(
        [OrchidDocument(page_content="delete me", id="doc-del")],
        namespace="kb",
    )
    await writer.delete(["doc-del"], namespace="kb")
    results = await store.reader().retrieve("delete", namespace="kb", k=1)
    assert results == []


async def test_scope_filtering(store: InMemoryVectorStore) -> None:
    scope = OrchidRAGScope(tenant_id="t1", user_id="u1")
    seed_documents(
        store,
        "kb",
        [
            OrchidDocument(page_content="tenant doc", id="doc-t"),
            OrchidDocument(page_content="user doc", id="doc-u"),
        ],
        scope=scope,
    )
    results = await store.reader().retrieve("doc", namespace="kb", k=5, scope=scope)
    assert len(results) == 2


async def test_metadata_filtering(store: InMemoryVectorStore) -> None:
    docs = [
        OrchidDocument(
            page_content="Italian pasta", id="doc-i", metadata={"cuisine": "italian"}
        ),
        OrchidDocument(
            page_content="Japanese sushi", id="doc-j", metadata={"cuisine": "japanese"}
        ),
    ]
    seed_documents(store, "recipes", docs)
    results = await store.reader().retrieve(
        "food",
        namespace="recipes",
        k=2,
        metadata_filters={"cuisine": "italian"},
    )
    assert len(results) == 1
    assert results[0].document.id == "doc-i"


async def test_repository_is_reader_and_writer(store: InMemoryVectorStore) -> None:
    repo = store.repository()
    assert isinstance(repo, OrchidVectorReader)
    assert isinstance(repo, OrchidVectorWriter)
    await repo.index(
        [OrchidDocument(page_content="combined repo doc", id="doc-repo")],
        namespace="repo",
    )
    results = await repo.retrieve("combined", namespace="repo", k=1)
    assert len(results) == 1
    assert results[0].document.id == "doc-repo"
