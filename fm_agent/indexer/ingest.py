"""Docs ingestion pass — walk filesystem, chunk, scan secrets, upsert.

Per SPEC §3: each repo → namespace mapping, headered/semantic strategies
per doc type, secret scanning, metadata attachment.
"""

from __future__ import annotations

import logging
from pathlib import Path

from orchid_ai.core.repository import OrchidDocument
from orchid_ai.documents.strategies import (
    HeaderedIngestion,
    HierarchicalIngestion,
    RecursiveIngestion,
    SemanticIngestion,
)

from .bootstrap import IndexerContext
from .manifest import ManifestRow, make_doc_id, make_tree_hash
from .secrets import SecretScanner
from .walker import RepoWalker, WalkedFile

logger = logging.getLogger(__name__)

INGESTION_STRATEGIES: dict[str, type] = {
    "headered": HeaderedIngestion,
    "hierarchical": HierarchicalIngestion,
    "semantic": SemanticIngestion,
    "recursive": RecursiveIngestion,
}


async def _ingest_file(
    ctx: IndexerContext,
    wfile: WalkedFile,
    walker: RepoWalker,
    scanner: SecretScanner,
    commit_sha: str = "",
) -> tuple[int, int, int]:
    """Ingest a single file. Returns (chunks, secret_findings_count, already_current)."""
    content = Path(wfile.absolute_path).read_bytes()
    tree_hash = make_tree_hash(content)

    should_skip = await ctx.manifest.should_skip(
        wfile.repo, wfile.relative_path, "docs", tree_hash,
    )
    if should_skip:
        logger.debug("Skipping unchanged: %s/%s", wfile.repo, wfile.relative_path)
        return 0, 0, 1

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except UnicodeDecodeError:
            logger.warning("Cannot decode: %s/%s", wfile.repo, wfile.relative_path)
            return 0, 0, 0

    if not text.strip():
        return 0, 0, 0

    scan_result = scanner.scan(text, path=f"{wfile.repo}/{wfile.relative_path}")
    if scanner.should_skip_chunk(scan_result):
        logger.warning("Skipping heavily redacted file: %s/%s (%.0f%%)",
                       wfile.repo, wfile.relative_path, scan_result.redacted_ratio * 100)
        return 0, 1, 0

    text = scan_result.cleaned_text

    strategy_name = walker.get_ingestion_strategy(wfile.namespace, wfile.doc_type)
    strategy_cls = INGESTION_STRATEGIES.get(strategy_name, HeaderedIngestion)
    strategy = strategy_cls()

    chunks = await strategy.ingest(
        text=text,
        filename=wfile.relative_path,
        scope=ctx.scope,
    )

    documents: list[OrchidDocument] = []
    for i, chunk in enumerate(chunks):
        doc_id = make_doc_id(wfile.repo, wfile.relative_path, i)
        metadata = dict(chunk.metadata)
        metadata.update({
            "repo": wfile.repo,
            "path": wfile.relative_path,
            "branch": "develop",
            "commit_sha": commit_sha,
            "doc_type": wfile.doc_type,
            "service": wfile.namespace.replace("svc-", ""),
            "authority": "code" if wfile.doc_type in ("readme", "api", "config") else "doc",
        })
        documents.append(OrchidDocument(
            id=doc_id,
            page_content=chunk.text,
            metadata=metadata,
        ))

    if documents:
        await ctx.writer.upsert(documents, wfile.namespace)

    findings_text = "; ".join(f"{f.rule}" for f in scan_result.findings) if scan_result.findings else ""
    await ctx.manifest.upsert(ManifestRow(
        repo=wfile.repo,
        path=wfile.relative_path,
        pass_type="docs",
        commit_sha=commit_sha,
        tree_hash=tree_hash,
        chunks=len(documents),
        secret_findings=findings_text,
    ))

    logger.info("Ingested: %s/%s → %s (%d chunks)", wfile.repo, wfile.relative_path, wfile.namespace, len(documents))
    return len(documents), len(scan_result.findings) if scan_result.dirty else 0, 0


async def ingest_docs(
    ctx: IndexerContext,
    repo_paths: list[str],
    exclusions_path: str = "examples/fm_agent/corpus/exclusions.yml",
) -> None:
    """Run the docs ingestion pass.  Prints per-namespace stats."""
    from .walker import ExclusionConfig

    exclusions = ExclusionConfig.from_file(exclusions_path)
    walker = RepoWalker(exclusions)
    scanner = SecretScanner()

    all_files: list[WalkedFile] = []
    for repo_path in repo_paths:
        wfiles = walker.walk_repo(repo_path)
        all_files.extend(wfiles)

    logger.info("Docs pass: %d files to process across %d repos", len(all_files), len(repo_paths))

    total_chunks = 0
    total_secrets = 0
    total_skipped = 0
    namespace_counts: dict[str, int] = {}

    for wfile in all_files:
        chunks, secrets, skipped = await _ingest_file(ctx, wfile, walker, scanner)
        total_chunks += chunks
        total_secrets += secrets
        total_skipped += skipped
        namespace_counts[wfile.namespace] = namespace_counts.get(wfile.namespace, 0) + chunks

    logger.info("Docs pass complete: %d chunks indexed, %d files skipped (unchanged), %d secret findings",
                total_chunks, total_skipped, total_secrets)

    print("\nPer-namespace ingestion counts:")
    for ns, count in sorted(namespace_counts.items()):
        print(f"  {ns}: {count} chunks")
    print(f"\nTotal: {total_chunks} chunks, {total_skipped} files unchanged, {total_secrets} secret findings")
