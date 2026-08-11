"""Bootstrap helpers for the FM indexer.

Connects to the Orchid runtime, provides the vector writer, Postgres pool,
and manifest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import asyncpg
from orchid_ai.core.repository import OrchidVectorWriter
from orchid_ai.rag.scopes import OrchidRAGScope

from .manifest import IndexerManifest

if TYPE_CHECKING:
    from orchid_ai import Orchid

logger = logging.getLogger(__name__)


@dataclass
class IndexerContext:
    """Holds all backend connections for an indexer run."""

    orchid: Orchid
    writer: OrchidVectorWriter
    manifest: IndexerManifest
    pool: asyncpg.Pool
    scope: OrchidRAGScope
    dsn: str


async def bootstrap_indexer(
    config_path: str = "examples/fm_agent/config/orchid.yml",
    dsn: str = "",
) -> IndexerContext:
    """Bootstrap Orchid + Postgres pool for the indexer.

    Parameters
    ----------
    config_path : Path to orchid.yml
    dsn : Postgres DSN for the manifest table. Defaults to the storage DSN
          from orchid.yml.
    """
    from orchid_ai import Orchid

    orchid = await Orchid.from_config_path(config_path)
    reader = orchid.runtime.get_reader()
    if not isinstance(reader, OrchidVectorWriter):
        raise TypeError("Configured vector backend does not support writing.")


    if not dsn:
        dsn = _extract_dsn_from_config(config_path)

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    manifest = IndexerManifest(pool)
    await manifest.init_db()

    scope = OrchidRAGScope(tenant_id="docebo")  # SPEC §3: tenant-wide for all platform knowledge

    logger.info("Indexer bootstrapped: dsn=%s", _redact_dsn(dsn))
    return IndexerContext(
        orchid=orchid,
        writer=reader,
        manifest=manifest,
        pool=pool,
        scope=scope,
        dsn=dsn,
    )


async def close_indexer(ctx: IndexerContext) -> None:
    await ctx.manifest.close()
    await ctx.pool.close()
    await ctx.orchid.close()


def _extract_dsn_from_config(config_path: str) -> str:
    """Extract Postgres DSN from orchid.yml storage block."""
    import yaml

    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    storage = data.get("storage", {})
    dsn = storage.get("dsn", "")
    if dsn:
        return dsn
    return "postgresql://orchid:orchid@localhost:5432/orchid"


def _redact_dsn(dsn: str) -> str:
    import re

    return re.sub(r"://[^:]+:[^@]+@", "://***:***@", dsn)
