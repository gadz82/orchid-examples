"""REST API endpoint for fm-indexer operations.

Discovered by orchid-api via the ``orchid_api.routers`` entry-point
group declared in ``pyproject.toml``.  Exposes ``POST /indexer/run``
which delegates to the ``examples.fm_agent.indexer`` modules.

Requires ``ALLOW_INDEX_ENDPOINT=true`` (same gate as ``POST /index``).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from orchid_ai.core.repository import OrchidVectorWriter
from orchid_ai.runtime import OrchidRuntime
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["indexer"])


class IndexerRunRequest(BaseModel):
    subcommand: str = "docs"
    repo_paths: list[str] = []
    force: bool = False
    dsn: str = ""


class IndexerRunResponse(BaseModel):
    status: str
    subcommand: str
    details: dict[str, Any] = {}
    error: str = ""


def _get_runtime() -> OrchidRuntime:
    from orchid_api.context import app_ctx

    return app_ctx.runtime


def _check_settings() -> None:
    from orchid_api.settings import get_settings

    settings = get_settings()
    if not settings.allow_index_endpoint:
        raise HTTPException(
            status_code=403,
            detail="The indexer endpoint is disabled. Set ALLOW_INDEX_ENDPOINT=true to enable.",
        )


@router.post("/indexer/run", response_model=IndexerRunResponse)
async def indexer_run(
    request: IndexerRunRequest,
    runtime: Annotated[OrchidRuntime, Depends(_get_runtime)],
) -> IndexerRunResponse:
    """Run an fm-indexer pass (docs, cards, kb, prune) via the API."""
    _check_settings()

    reader = runtime.get_reader()
    if not isinstance(reader, OrchidVectorWriter):
        raise HTTPException(status_code=503, detail="Vector store does not support writing (backend may be 'null')")

    from orchid_api.settings import get_settings

    dsn = get_settings().chat_db_dsn or request.dsn
    if not dsn:
        raise HTTPException(status_code=400, detail="No Postgres DSN configured")

    subcommand = request.subcommand.lower()
    repo_paths = [p for p in request.repo_paths if p]

    if subcommand not in ("docs", "cards", "kb", "prune", "graph"):
        raise HTTPException(status_code=400, detail=f"Unknown subcommand: {subcommand}")

    if subcommand in ("docs", "cards", "prune", "graph") and not repo_paths:
        raise HTTPException(status_code=400, detail=f"repo_paths required for {subcommand} pass")

    try:
        if subcommand == "docs":
            details = await _docs(reader, dsn, repo_paths)
        elif subcommand == "cards":
            details = await _cards(reader, dsn, repo_paths, force=request.force)
        elif subcommand == "kb":
            details = await _kb(reader, dsn)
        elif subcommand == "graph":
            details = await _graph(reader, repo_paths)
        else:
            details = await _prune(reader, dsn, repo_paths)

        return IndexerRunResponse(status="ok", subcommand=subcommand, details=details)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("/indexer/run %s failed", subcommand)
        raise HTTPException(status_code=500, detail=str(exc))


async def _docs(writer: Any, dsn: str, repo_paths: list[str]) -> dict[str, Any]:
    from pathlib import Path

    import asyncpg
    from orchid_ai.core.repository import OrchidDocument
    from orchid_ai.rag.scopes import OrchidRAGScope

    from examples.fm_agent.indexer.ingest import INGESTION_STRATEGIES
    from examples.fm_agent.indexer.manifest import IndexerManifest, ManifestRow, make_doc_id, make_tree_hash
    from examples.fm_agent.indexer.secrets import SecretScanner
    from examples.fm_agent.indexer.walker import ExclusionConfig, RepoWalker

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    manifest = IndexerManifest(pool)
    await manifest.init_db()
    scope = OrchidRAGScope(tenant_id="docebo")

    try:
        exclusions = ExclusionConfig.from_file("examples/fm_agent/corpus/exclusions.yml")
        walker = RepoWalker(exclusions)
        scanner = SecretScanner()

        all_files = []
        for rp in repo_paths:
            all_files.extend(walker.walk_repo(rp))

        total_chunks = 0
        total_skipped = 0
        total_secrets = 0
        ns_counts: dict[str, int] = {}

        for wfile in all_files:
            content = Path(wfile.absolute_path).read_bytes()
            tree_hash = make_tree_hash(content)

            should_skip = await manifest.should_skip(wfile.repo, wfile.relative_path, "docs", tree_hash)
            if should_skip:
                total_skipped += 1
                continue

            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    text = content.decode("latin-1")
                except UnicodeDecodeError:
                    continue
            if not text.strip():
                continue

            scan_result = scanner.scan(text, path=f"{wfile.repo}/{wfile.relative_path}")
            if scanner.should_skip_chunk(scan_result):
                total_secrets += len(scan_result.findings)
                continue

            text = scan_result.cleaned_text
            strategy_name = walker.get_ingestion_strategy(wfile.namespace, wfile.doc_type)
            strategy_cls = INGESTION_STRATEGIES.get(strategy_name)
            if strategy_cls is None:
                from orchid_ai.documents.strategies import HeaderedIngestion

                strategy_cls = HeaderedIngestion
            strategy = strategy_cls()
            chunks = await strategy.ingest(text=text, filename=wfile.relative_path, scope=scope)

            documents = []
            for i, chunk in enumerate(chunks):
                doc_id = make_doc_id(wfile.repo, wfile.relative_path, i)
                metadata = dict(chunk.metadata)
                metadata.update({
                    "repo": wfile.repo,
                    "path": wfile.relative_path,
                    "branch": "develop",
                    "doc_type": wfile.doc_type,
                    "service": wfile.namespace.replace("svc-", ""),
                    "authority": "code",
                })
                documents.append(OrchidDocument(id=doc_id, page_content=chunk.text, metadata=metadata))

            if documents:
                await writer.upsert(documents, wfile.namespace)

            findings_text = "; ".join(f"{f.rule}" for f in scan_result.findings) if scan_result.findings else ""
            await manifest.upsert(ManifestRow(
                repo=wfile.repo, path=wfile.relative_path, pass_type="docs",
                tree_hash=tree_hash, chunks=len(documents), secret_findings=findings_text,
            ))
            total_chunks += len(documents)
            ns_counts[wfile.namespace] = ns_counts.get(wfile.namespace, 0) + len(documents)

        return {
            "chunks_indexed": total_chunks,
            "files_unchanged": total_skipped,
            "secret_findings": total_secrets,
            "per_namespace": ns_counts,
        }
    finally:
        await pool.close()


async def _cards(writer: Any, dsn: str, repo_paths: list[str], force: bool) -> dict[str, Any]:
    import json
    from os import path as _ospath
    from pathlib import Path

    import asyncpg
    from orchid_ai.core.repository import OrchidDocument
    from orchid_ai.rag.scopes import OrchidRAGScope

    from examples.fm_agent.indexer.bootstrap import IndexerContext
    from examples.fm_agent.indexer.cards import (
        _generate_card,
        _list_module_dirs,
        _module_tree_hash,
        _resolve_cards_namespace,
    )
    from examples.fm_agent.indexer.manifest import IndexerManifest, ManifestRow, make_doc_id

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    manifest = IndexerManifest(pool)
    await manifest.init_db()
    scope = OrchidRAGScope(tenant_id="docebo")

    ctx = IndexerContext(orchid=None, writer=writer, manifest=manifest, pool=pool, scope=scope, dsn=dsn)

    total_cards = 0
    total_skipped = 0

    try:
        for repo_path in repo_paths:
            repo_name = _ospath.basename(repo_path.rstrip("/"))
            modules = _list_module_dirs(repo_path)

            for module_path in modules:
                module_rel = str(Path(module_path).relative_to(repo_path))
                tree_hash = _module_tree_hash(module_path)

                if not force:
                    should_skip = await manifest.should_skip(repo_name, module_rel, "cards", tree_hash)
                    if should_skip:
                        total_skipped += 1
                        continue

                card = await _generate_card(ctx, repo_name, module_path)
                if card is None:
                    continue

                card_text = json.dumps(card, indent=2)
                namespace = _resolve_cards_namespace(repo_name)
                doc_id = make_doc_id(repo_name, module_rel, 0)

                doc = OrchidDocument(
                    id=doc_id,
                    page_content=card_text,
                    metadata={
                        "tenant_id": scope.tenant_id,
                        "scope": "tenant",
                        "repo": repo_name,
                        "path": module_rel,
                        "doc_type": "derived-card",
                        "authority": "code",
                        "branch": "develop",
                    },
                )
                await writer.upsert([doc], namespace)

                await manifest.upsert(ManifestRow(
                    repo=repo_name, path=module_rel, pass_type="cards",
                    tree_hash=tree_hash, doc_id=doc_id, chunks=1,
                ))
                total_cards += 1
    finally:
        await pool.close()

    return {"cards_generated": total_cards, "cards_unchanged": total_skipped}


async def _kb(writer: Any, dsn: str) -> dict[str, Any]:
    import asyncpg
    from orchid_ai.rag.scopes import OrchidRAGScope

    from examples.fm_agent.indexer.bootstrap import IndexerContext
    from examples.fm_agent.indexer.kb import HelpCenterCrawler
    from examples.fm_agent.indexer.manifest import IndexerManifest

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    manifest = IndexerManifest(pool)
    await manifest.init_db()
    scope = OrchidRAGScope(tenant_id="docebo")

    try:
        ctx = IndexerContext(orchid=None, writer=writer, manifest=manifest, pool=pool, scope=scope, dsn=dsn)
        crawler = HelpCenterCrawler.from_config(ctx)
        stats = await crawler.crawl()
        return {"articles_per_section": stats}
    finally:
        await pool.close()


async def _prune(writer: Any, dsn: str, repo_paths: list[str]) -> dict[str, Any]:
    import asyncpg
    from orchid_ai.rag.scopes import OrchidRAGScope

    from examples.fm_agent.indexer.bootstrap import IndexerContext
    from examples.fm_agent.indexer.manifest import IndexerManifest
    from examples.fm_agent.indexer.prune import prune_deleted_files

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    manifest = IndexerManifest(pool)
    await manifest.init_db()
    scope = OrchidRAGScope(tenant_id="docebo")

    try:
        ctx = IndexerContext(orchid=None, writer=writer, manifest=manifest, pool=pool, scope=scope, dsn=dsn)
        pruned = await prune_deleted_files(ctx, repo_paths)
        return {"paths_pruned": pruned}
    finally:
        await pool.close()


async def _graph(writer: Any, repo_paths: list[str]) -> dict[str, Any]:
    import os as _os

    from orchid_ai.core.repository import OrchidDocument
    from orchid_ai.rag.scopes import OrchidRAGScope
    from orchid_rag_neo4j.neo4j_graph import Neo4jGraphStore

    from examples.fm_agent.indexer.graph import GraphExtractor

    scope = OrchidRAGScope(tenant_id="docebo")
    graph_store = Neo4jGraphStore(
        url="bolt://neo4j:7687",
        username="neo4j",
        password="Password123",
    )

    total_entities = 0
    total_edges = 0
    all_cards: list[str] = []

    try:
        for repo_path in repo_paths:
            repo_name = _os.path.basename(repo_path.rstrip("/"))
            extractor = GraphExtractor(repo_name, repo_path)
            await extractor.extract()

            if extractor.entities:
                await graph_store.upsert_entities(extractor.entities, scope)
                total_entities += len(extractor.entities)

            if extractor.edges:
                await graph_store.upsert_edges(extractor.edges, scope)
                total_edges += len(extractor.edges)

            cards = extractor.serialize_cards()
            all_cards.extend(cards)
            logger.info("Graph: %s → %d entities, %d edges, %d cards", repo_name, len(extractor.entities), len(extractor.edges), len(cards))

        if all_cards:
            documents = []
            for i, card_text in enumerate(all_cards):
                doc_id = f"platform-graph|card|{i}"
                documents.append(OrchidDocument(
                    id=doc_id,
                    page_content=card_text,
                    metadata={
                        "tenant_id": scope.tenant_id,
                        "scope": "tenant",
                        "doc_type": "platform-graph-card",
                        "namespace": "platform-graph",
                    },
                ))
            await writer.upsert(documents, "platform-graph")
            logger.info("Graph cards: %d serialized to platform-graph", len(documents))

    finally:
        await graph_store.close()

    return {
        "entities": total_entities,
        "edges": total_edges,
        "cards": len(all_cards),
    }
