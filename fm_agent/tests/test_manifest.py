"""Tests for the Postgres-backed idempotency manifest."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from examples.fm_agent.indexer.manifest import IndexerManifest, ManifestRow, make_doc_id, make_tree_hash


class TestManifestHelpers:
    """Cover deterministic ID/hash helpers."""

    def test_make_doc_id_is_deterministic(self) -> None:
        a = make_doc_id("repo", "path/to/file.md", 3)
        b = make_doc_id("repo", "path/to/file.md", 3)
        c = make_doc_id("repo", "path/to/file.md", 4)

        assert a == b
        assert a != c
        assert len(a) == 64

    def test_make_tree_hash_is_deterministic(self) -> None:
        content = b"hello world"
        assert make_tree_hash(content) == make_tree_hash(content)
        assert make_tree_hash(content) != make_tree_hash(b"hello world2")


class TestIndexerManifest:
    """Cover should_skip / upsert / delete / list_paths with a mocked pool."""

    @pytest.fixture
    def manifest(self):
        conn = AsyncMock()

        class FakeContext:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, exc_type, exc, tb):
                return False

        class FakePool:
            def acquire(self):
                return FakeContext()

        return IndexerManifest(FakePool()), conn

    def _set_fetchrow(self, manifest_conn, return_value):
        _manifest, conn = manifest_conn
        conn.fetchrow = AsyncMock(return_value=return_value)

    def _set_execute(self, manifest_conn):
        _manifest, conn = manifest_conn
        conn.execute = AsyncMock()
        return conn.execute

    def _set_fetch(self, manifest_conn, return_value):
        _manifest, conn = manifest_conn
        conn.fetch = AsyncMock(return_value=return_value)

    async def test_should_skip_when_unchanged(self, manifest) -> None:
        self._set_fetchrow(manifest,
            return_value={
                "repo": "r", "path": "p", "pass_type": "docs",
                "commit_sha": "abc", "tree_hash": "hash1", "doc_id": "d1",
                "chunks": 2, "secret_findings": "", "indexed_at": None,
            }
        )
        m, _conn = manifest
        result = await m.should_skip("r", "p", "docs", "hash1")
        assert result is True

    async def test_should_not_skip_when_changed(self, manifest) -> None:
        self._set_fetchrow(manifest,
            return_value={
                "repo": "r", "path": "p", "pass_type": "docs",
                "commit_sha": "abc", "tree_hash": "old_hash", "doc_id": "d1",
                "chunks": 2, "secret_findings": "", "indexed_at": None,
            }
        )
        m, _conn = manifest
        result = await m.should_skip("r", "p", "docs", "new_hash")
        assert result is False

    async def test_should_not_skip_when_missing(self, manifest) -> None:
        self._set_fetchrow(manifest, return_value=None)
        m, _conn = manifest
        result = await m.should_skip("r", "p", "docs", "hash1")
        assert result is False

    async def test_upsert_executes_upsert_sql(self, manifest) -> None:
        execute = self._set_execute(manifest)
        m, _conn = manifest

        row = ManifestRow(repo="r", path="p", pass_type="docs", tree_hash="hash1", chunks=2)
        await m.upsert(row)

        execute.assert_awaited_once()
        call_args = execute.call_args
        assert "INSERT INTO indexer_manifest" in call_args.args[0]
        assert "ON CONFLICT" in call_args.args[0]

    async def test_delete_executes_delete_sql(self, manifest) -> None:
        execute = self._set_execute(manifest)
        m, _conn = manifest

        await m.delete("r", "p")
        execute.assert_awaited_once()
        call_args = execute.call_args
        assert "DELETE FROM indexer_manifest" in call_args.args[0]

    async def test_list_paths_returns_set(self, manifest) -> None:
        self._set_fetch(manifest, return_value=[{"path": "a.md"}, {"path": "b.md"}])
        m, _conn = manifest

        result = await m.list_paths("r", "docs")
        assert result == {"a.md", "b.md"}
