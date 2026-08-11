"""fm-indexer CLI — Corpus builder entry point.

Subcommands::

    fm-indexer docs <repo-path>...   — ingest markdown/OpenAPI/config docs
    fm-indexer cards <repo-path>...  — generate derived module cards via Gemini
    fm-indexer kb                    — crawl Help Center sections
    fm-indexer graph <repo-path>...  — extract platform dependency graph
    fm-indexer prune <repo-path>...  — remove vectors for deleted files

For raw Markdown exports with YAML front-matter, use the framework CLI::

    orchid index dir <path> -n <namespace> --front-matter --id-field <field>

All passes are idempotent.  Running twice is a no‑op.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

import typer

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)

app = typer.Typer(
    name="fm-indexer",
    help="FM Agent corpus builder — idempotent ingestion + cards + KB crawler.",
    no_args_is_help=True,
)

_docs_app = typer.Typer(help="Ingest documentation files (markdown, OpenAPI, config).")
_cards_app = typer.Typer(help="Generate derived module cards via Gemini Flash.")
_kb_app = typer.Typer(help="Crawl Help Center sections.")
_graph_app = typer.Typer(help="Extract platform dependency graph into Neo4j + Qdrant.")
_prune_app = typer.Typer(help="Remove vectors for files no longer present.")

app.add_typer(_docs_app, name="docs")
app.add_typer(_cards_app, name="cards")
app.add_typer(_kb_app, name="kb")
app.add_typer(_graph_app, name="graph")
app.add_typer(_prune_app, name="prune")


def _resolve_config(config: str) -> str:
    if config:
        return config
    return "examples/fm_agent/config/orchid.yml"


def _resolve_dsn(dsn: str, config_path: str) -> str:
    if dsn:
        return dsn
    import yaml

    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return data.get("storage", {}).get("dsn", "postgresql://orchid:orchid@localhost:5432/orchid")
    except OSError:
        return "postgresql://orchid:orchid@localhost:5432/orchid"


@_docs_app.callback(invoke_without_command=False)
def docs_help() -> None:
    pass


@_docs_app.command("run")
def docs_run(
    repo_paths: Annotated[list[str], typer.Argument(help="Repository paths to index")],
    config: Annotated[str, typer.Option("--config", "-c", help="Path to orchid.yml")] = "",
    dsn: Annotated[str, typer.Option("--dsn", help="Postgres DSN for manifest")] = "",
    exclusions: Annotated[str, typer.Option("--exclusions", help="Path to exclusions.yml")] = "examples/fm_agent/corpus/exclusions.yml",
) -> None:
    """Walk repos and ingest docs into RAG namespaces."""
    config_path = _resolve_config(config)
    resolved_dsn = _resolve_dsn(dsn, config_path)

    async def _run() -> None:
        from ..indexer.bootstrap import bootstrap_indexer, close_indexer
        from ..indexer.ingest import ingest_docs

        ctx = await bootstrap_indexer(config_path, resolved_dsn)
        try:
            await ingest_docs(ctx, list(repo_paths), exclusions)
        finally:
            await close_indexer(ctx)

    asyncio.run(_run())


@_cards_app.callback(invoke_without_command=False)
def cards_help() -> None:
    pass


@_cards_app.command("run")
def cards_run(
    repo_paths: Annotated[list[str], typer.Argument(help="Repository paths for card generation")],
    config: Annotated[str, typer.Option("--config", "-c", help="Path to orchid.yml")] = "",
    dsn: Annotated[str, typer.Option("--dsn", help="Postgres DSN for manifest")] = "",
    force: Annotated[bool, typer.Option("--force", "-f", help="Regenerate all cards, ignoring manifest")] = False,
) -> None:
    """Generate derived service/module cards via Gemini Flash."""
    config_path = _resolve_config(config)
    resolved_dsn = _resolve_dsn(dsn, config_path)

    async def _run() -> None:
        from ..indexer.bootstrap import bootstrap_indexer, close_indexer
        from ..indexer.cards import generate_cards, generate_endpoint_cards

        ctx = await bootstrap_indexer(config_path, resolved_dsn)
        try:
            await generate_cards(ctx, list(repo_paths), force=force)
            await generate_endpoint_cards(ctx, list(repo_paths), force=force)
        finally:
            await close_indexer(ctx)

    asyncio.run(_run())


@_kb_app.callback(invoke_without_command=False)
def kb_help() -> None:
    pass


@_kb_app.command("run")
def kb_run(
    config: Annotated[str, typer.Option("--config", "-c", help="Path to orchid.yml")] = "",
    dsn: Annotated[str, typer.Option("--dsn", help="Postgres DSN for manifest")] = "",
    kb_config: Annotated[str, typer.Option("--kb-config", help="Path to KB config YAML")] = "examples/fm_agent/corpus/exclusions.yml",
) -> None:
    """Crawl Help Center sections into product-kb namespace."""
    config_path = _resolve_config(config)
    resolved_dsn = _resolve_dsn(dsn, config_path)

    async def _run() -> None:
        from ..indexer.bootstrap import bootstrap_indexer, close_indexer
        from ..indexer.kb import HelpCenterCrawler

        ctx = await bootstrap_indexer(config_path, resolved_dsn)
        try:
            crawler = HelpCenterCrawler.from_config(ctx, kb_config)
            stats = await crawler.crawl()
            print("\nKB crawl results:")
            for section, count in sorted(stats.items()):
                print(f"  {section}: {count} articles")
        finally:
            await close_indexer(ctx)

    asyncio.run(_run())


@_prune_app.callback(invoke_without_command=False)
def prune_help() -> None:
    pass


@_prune_app.command("run")
def prune_run(
    repo_paths: Annotated[list[str], typer.Argument(help="Repository paths to prune")],
    config: Annotated[str, typer.Option("--config", "-c", help="Path to orchid.yml")] = "",
    dsn: Annotated[str, typer.Option("--dsn", help="Postgres DSN for manifest")] = "",
    exclusions: Annotated[str, typer.Option("--exclusions", help="Path to exclusions.yml")] = "examples/fm_agent/corpus/exclusions.yml",
) -> None:
    """Remove vectors and manifest entries for files no longer present in repos."""
    config_path = _resolve_config(config)
    resolved_dsn = _resolve_dsn(dsn, config_path)

    async def _run() -> None:
        from ..indexer.bootstrap import bootstrap_indexer, close_indexer
        from ..indexer.prune import prune_deleted_files

        ctx = await bootstrap_indexer(config_path, resolved_dsn)
        try:
            pruned = await prune_deleted_files(ctx, list(repo_paths), exclusions)
            print(f"Pruned {pruned} deleted paths")
        finally:
            await close_indexer(ctx)

    asyncio.run(_run())


@_graph_app.callback(invoke_without_command=False)
def graph_help() -> None:
    pass


@_graph_app.command("run")
def graph_run(
    repo_paths: Annotated[list[str], typer.Argument(help="Repository paths for graph extraction")],
    config: Annotated[str, typer.Option("--config", "-c", help="Path to orchid.yml")] = "",
    dsn: Annotated[str, typer.Option("--dsn", help="Postgres DSN for manifest")] = "",
    neo4j_uri: Annotated[str, typer.Option("--neo4j-uri", help="Neo4j bolt URI")] = "bolt://localhost:7687",
    neo4j_user: Annotated[str, typer.Option("--neo4j-user", help="Neo4j username")] = "neo4j",
    neo4j_password: Annotated[str, typer.Option("--neo4j-password", help="Neo4j password")] = "Password123",
) -> None:
    """Extract platform dependency graph into Neo4j + Qdrant platform-graph."""
    config_path = _resolve_config(config)
    resolved_dsn = _resolve_dsn(dsn, config_path)

    async def _run() -> None:
        from orchid_ai.core.repository import OrchidDocument
        from orchid_ai.rag.scopes import OrchidRAGScope
        from orchid_rag_neo4j.neo4j_graph import Neo4jGraphStore

        from ..indexer.bootstrap import bootstrap_indexer, close_indexer
        from ..indexer.graph import GraphExtractor

        ctx = await bootstrap_indexer(config_path, resolved_dsn)
        try:
            scope = OrchidRAGScope(tenant_id="docebo")
            graph_store = Neo4jGraphStore(
                url=neo4j_uri,
                username=neo4j_user,
                password=neo4j_password,
            )

            total_entities = 0
            total_edges = 0
            all_cards: list[str] = []

            for repo_path in repo_paths:
                import os as _os

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

            # Serialize cards into platform-graph Qdrant namespace
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
                await ctx.writer.upsert(documents, "platform-graph")
                logger.info("Graph cards: %d serialized to platform-graph", len(documents))

            print(f"\nGraph pass: {total_entities} entities, {total_edges} edges, {len(all_cards)} cards")
        finally:
            await graph_store.close()
            await close_indexer(ctx)

    asyncio.run(_run())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
