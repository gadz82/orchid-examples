"""Postgres manifest table for idempotent indexing.

Tracks every ingested file with ``(repo, path, commit_sha, tree_hash,
indexed_at)`` so unchanged files are skipped and deleted files are
pruned.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

CREATE_MANIFEST_SQL = """
CREATE TABLE IF NOT EXISTS indexer_manifest (
    id          SERIAL PRIMARY KEY,
    repo        TEXT NOT NULL,
    path        TEXT NOT NULL,
    pass_type   TEXT NOT NULL DEFAULT 'docs',
    commit_sha  TEXT,
    tree_hash   TEXT,
    doc_id      TEXT,
    chunks      INTEGER NOT NULL DEFAULT 0,
    indexed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    secret_findings TEXT,
    UNIQUE (repo, path, pass_type)
)
"""

CREATE_MANIFEST_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_manifest_repo_path
    ON indexer_manifest (repo, path)
"""

DOC_ID_NAMESPACE = hashlib.sha256(b"orchid-fm-indexer").digest()


@dataclass
class ManifestRow:
    repo: str
    path: str
    pass_type: str = "docs"
    commit_sha: str = ""
    tree_hash: str = ""
    doc_id: str = ""
    chunks: int = 0
    secret_findings: str = ""


def make_doc_id(repo: str, path: str, chunk_ordinal: int = 0) -> str:
    """Deterministic document ID = sha256(repo + path + chunk_ordinal)."""
    digest = hashlib.sha256(f"{repo}|{path}|{chunk_ordinal}".encode()).digest()
    return hashlib.sha256(DOC_ID_NAMESPACE + digest).hexdigest()


def make_tree_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class IndexerManifest:
    """Idempotent ingestion manifest backed by a Postgres table."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def init_db(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(CREATE_MANIFEST_SQL)
            await conn.execute(CREATE_MANIFEST_INDEX_SQL)

    async def get_row(self, repo: str, path: str, pass_type: str = "docs") -> ManifestRow | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT repo, path, pass_type, commit_sha, tree_hash, doc_id, chunks, secret_findings "
                "FROM indexer_manifest WHERE repo=$1 AND path=$2 AND pass_type=$3",
                repo, path, pass_type,
            )
            if row is None:
                return None
            return ManifestRow(
                repo=row["repo"],
                path=row["path"],
                pass_type=row["pass_type"],
                commit_sha=row["commit_sha"] or "",
                tree_hash=row["tree_hash"] or "",
                doc_id=row["doc_id"] or "",
                chunks=row["chunks"],
                secret_findings=row["secret_findings"] or "",
            )

    async def should_skip(self, repo: str, path: str, pass_type: str, tree_hash: str) -> bool:
        """Return True if the file is unchanged (same tree_hash) and should be skipped."""
        existing = await self.get_row(repo, path, pass_type)
        if existing is None:
            return False
        return existing.tree_hash == tree_hash

    async def upsert(self, row: ManifestRow) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO indexer_manifest (repo, path, pass_type, commit_sha, tree_hash, doc_id, chunks, secret_findings)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                   ON CONFLICT (repo, path, pass_type) DO UPDATE SET
                       commit_sha = EXCLUDED.commit_sha,
                       tree_hash = EXCLUDED.tree_hash,
                       doc_id = EXCLUDED.doc_id,
                       chunks = EXCLUDED.chunks,
                       indexed_at = NOW(),
                       secret_findings = EXCLUDED.secret_findings""",
                row.repo, row.path, row.pass_type,
                row.commit_sha, row.tree_hash, row.doc_id,
                row.chunks, row.secret_findings,
            )

    async def delete(self, repo: str, path: str, pass_type: str = "docs") -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM indexer_manifest WHERE repo=$1 AND path=$2 AND pass_type=$3",
                repo, path, pass_type,
            )

    async def list_paths(self, repo: str, pass_type: str = "docs") -> set[str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT path FROM indexer_manifest WHERE repo=$1 AND pass_type=$2",
                repo, pass_type,
            )
            return {row["path"] for row in rows}

    async def close(self) -> None:
        pass
