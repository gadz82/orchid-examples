"""In-memory vector store replacements for hermetic e2e tests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

import pytest
from orchid_ai.core.repository import (
    OrchidDocument,
    OrchidSearchResult,
    OrchidVectorReader,
    OrchidVectorStoreAdmin,
    OrchidVectorWriter,
)
from orchid_ai.core.scopes import OrchidRAGScope, resolve_scope_level


class InMemoryVectorReader(OrchidVectorReader):
    """Simple in-memory reader supporting keyword search + filters.

    This is **not** a real vector search; it scores documents by the number
    of query tokens they contain. It is sufficient for verifying that the
    right documents are retrieved and passed to agents.
    """

    def __init__(self, store: InMemoryVectorStore | None = None) -> None:
        self._store = store if store is not None else InMemoryVectorStore()

    @property
    def store(self) -> InMemoryVectorStore:
        return self._store

    async def retrieve(
        self,
        query: str,
        namespace: str,
        k: int = 5,
        scope: OrchidRAGScope | None = None,
        metadata_filters: dict[str, object] | None = None,
    ) -> list[OrchidSearchResult]:
        candidates = self._store.docs.get(namespace, [])
        scored: list[tuple[float, OrchidDocument]] = []
        query_tokens = set(_tokenize(query))

        for doc in candidates:
            if scope is not None and not _matches_scope(doc, scope):
                continue
            if metadata_filters and not _matches_metadata(doc, metadata_filters):
                continue
            score = _score_doc(doc, query_tokens)
            # Include docs that match explicit metadata filters even when
            # the keyword score is zero — this mirrors real vector backends.
            if score > 0 or metadata_filters:
                scored.append((score, doc))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            OrchidSearchResult(
                document=doc, score=min(1.0, score / max(1, len(query_tokens)))
            )
            for score, doc in scored[:k]
        ]

    async def retrieve_sparse(
        self,
        query_sparse: Any,
        namespace: str,
        k: int = 5,
        scope: OrchidRAGScope | None = None,
        metadata_filters: dict[str, object] | None = None,
    ) -> list[OrchidSearchResult]:
        # Degrade to dense-like keyword search for tests.
        return await self.retrieve(
            query=str(query_sparse),
            namespace=namespace,
            k=k,
            scope=scope,
            metadata_filters=metadata_filters,
        )


class InMemoryVectorWriter(OrchidVectorWriter):
    """Write documents into the in-memory store."""

    def __init__(self, store: InMemoryVectorStore | None = None) -> None:
        self._store = store if store is not None else InMemoryVectorStore()

    @property
    def store(self) -> InMemoryVectorStore:
        return self._store

    async def index(
        self,
        documents: list[OrchidDocument],
        namespace: str,
    ) -> None:
        self._store.upsert(namespace, documents)

    async def upsert(
        self,
        documents: list[OrchidDocument],
        namespace: str,
    ) -> None:
        self._store.upsert(namespace, documents)

    async def delete(
        self,
        document_ids: list[str],
        namespace: str,
    ) -> None:
        self._store.delete(namespace, document_ids)


class InMemoryVectorStoreAdmin(OrchidVectorStoreAdmin):
    """No-op admin for the in-memory store."""

    def __init__(self, store: InMemoryVectorStore | None = None) -> None:
        self._store = store if store is not None else InMemoryVectorStore()

    async def ensure_collections(self, namespaces: list[str]) -> None:
        for namespace in namespaces:
            self._store.docs.setdefault(namespace, [])


class InMemoryVectorRepository(InMemoryVectorReader, InMemoryVectorWriter):
    """Combined reader/writer for tests that exercise indexing and retrieval."""

    def __init__(self, store: InMemoryVectorStore | None = None) -> None:
        # Both parent classes share the same store reference; initialising
        # either one is enough because they both assign ``self._store``.
        InMemoryVectorReader.__init__(self, store)


class InMemoryVectorStore:
    """Shared document bucket used by reader, writer, and admin."""

    def __init__(self) -> None:
        self.docs: dict[str, list[OrchidDocument]] = {}

    def upsert(self, namespace: str, documents: Iterable[OrchidDocument]) -> None:
        existing = {
            doc.id: idx
            for idx, doc in enumerate(self.docs.get(namespace, []))
            if doc.id
        }
        for doc in documents:
            if doc.id and doc.id in existing:
                self.docs[namespace][existing[doc.id]] = doc
            else:
                self.docs.setdefault(namespace, []).append(doc)

    def delete(self, namespace: str, document_ids: list[str]) -> None:
        if namespace not in self.docs:
            return
        self.docs[namespace] = [
            doc for doc in self.docs[namespace] if doc.id not in document_ids
        ]

    def clear(self) -> None:
        self.docs.clear()

    def reader(self) -> InMemoryVectorReader:
        return InMemoryVectorReader(self)

    def writer(self) -> InMemoryVectorWriter:
        return InMemoryVectorWriter(self)

    def repository(self) -> InMemoryVectorRepository:
        return InMemoryVectorRepository(self)

    def admin(self) -> InMemoryVectorStoreAdmin:
        return InMemoryVectorStoreAdmin(self)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"\b\w+\b", text) if len(t) > 2]


def _score_doc(doc: OrchidDocument, query_tokens: set[str]) -> float:
    doc_tokens = set(_tokenize(doc.page_content))
    if not doc_tokens or not query_tokens:
        return 0.0
    return float(len(query_tokens & doc_tokens))


def _matches_scope(doc: OrchidDocument, scope: OrchidRAGScope) -> bool:
    metadata = doc.metadata or {}
    doc_scope = metadata.get("scope")
    if doc_scope is None:
        return True
    if doc_scope != resolve_scope_level(scope):
        return False
    # Scope fields must match where the doc scope level is specific.
    if doc_scope in ("chat_agent",) and metadata.get("agent_id") != scope.agent_id:
        return False
    if (
        doc_scope in ("chat_agent", "chat_shared")
        and metadata.get("chat_id") != scope.chat_id
    ):
        return False
    if (
        doc_scope in ("chat_agent", "chat_shared", "user")
        and metadata.get("user_id") != scope.user_id
    ):
        return False
    return metadata.get("tenant_id") == scope.tenant_id


def _matches_metadata(doc: OrchidDocument, filters: dict[str, object]) -> bool:
    metadata = doc.metadata or {}
    for key, value in filters.items():
        if key.startswith("_"):
            continue  # backend-specific extras ignored in memory
        actual = metadata.get(key)
        if isinstance(value, list):
            if actual not in value:
                return False
        elif isinstance(value, dict):
            if "contains" in value and (
                not isinstance(actual, list) or value["contains"] not in actual
            ):
                return False
            if "not" in value and actual == value["not"]:
                return False
            if "gte" in value and (actual is None or actual < value["gte"]):
                return False
            if "lte" in value and (actual is None or actual > value["lte"]):
                return False
        else:
            if actual != value:
                return False
    return True


def seed_documents(
    store: InMemoryVectorStore,
    namespace: str,
    documents: list[OrchidDocument],
    scope: OrchidRAGScope | None = None,
) -> None:
    """Populate an in-memory store with documents, tagging scope metadata."""
    if scope is not None:
        level = resolve_scope_level(scope)
        for doc in documents:
            doc.metadata = {
                **(doc.metadata or {}),
                "scope": level,
                "tenant_id": scope.tenant_id,
                "user_id": scope.user_id,
                "chat_id": scope.chat_id,
                "agent_id": scope.agent_id,
            }
    store.upsert(namespace, documents)


@pytest.fixture
def in_memory_vector_store() -> InMemoryVectorStore:
    """Fresh in-memory vector store for a test."""
    return InMemoryVectorStore()


@pytest.fixture
def mock_vector_reader(
    in_memory_vector_store: InMemoryVectorStore,
) -> InMemoryVectorReader:
    """Fresh in-memory vector reader."""
    return in_memory_vector_store.reader()


@pytest.fixture
def mock_vector_writer(
    in_memory_vector_store: InMemoryVectorStore,
) -> InMemoryVectorWriter:
    """Fresh in-memory vector writer."""
    return in_memory_vector_store.writer()
