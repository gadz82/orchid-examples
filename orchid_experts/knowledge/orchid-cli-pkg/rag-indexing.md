<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# RAG Indexing

The CLI provides commands for indexing documents into the vector store (ChromaDB or Qdrant) without needing the API server. These commands are essential for bootstrapping knowledge bases in development and production.

## Index Commands

### index file

Index a single file:

```bash
orchid index file document.pdf \
  --namespace my-namespace \
  --config orchid.yml
```

Supported formats: PDF (via PyMuPDF), DOCX (via python-docx), XLSX (via OpenPyXL), CSV (built-in), TXT, MD, and images (via vision model).

The file extension determines the parser. If the extension is unknown, the command fails with a clear error.

### index directory

Index all supported files in a directory:

```bash
orchid index directory ./knowledge/ \
  --namespace experts \
  --recursive
```

Options:
- `--recursive` — Include files in subdirectories.
- `--glob "*.md"` — Filter files by glob pattern.
- `--namespace` — Target RAG namespace (collection name).
- `--chunk-size 2000` — Override default chunk size (1000).
- `--chunk-overlap 400` — Override default chunk overlap (200).
- `--strategy recursive` — Ingestion strategy (recursive, semantic, hierarchical, headered).
- `--scope shared` — RAG scope level.
- `--reindex` — Delete existing namespace and re-index from scratch.

### index text

Index raw text directly:

```bash
echo "Knowledge content here..." | orchid index text \
  --namespace my-namespace \
  --filename "inline.md"
```

Or read from a pipe:

```bash
cat large_document.txt | orchid index text --namespace docs --filename "large_document.txt"
```

## Ingestion Strategy

The CLI defaults to `RecursiveIngestion` (character-based splitting via `\n\n → \n → . → word → char` hierarchy). Override with other strategies:

```bash
# Semantic: split on topic changes
orchid index directory ./docs/ --namespace docs --strategy semantic

# Headered: split on markdown headings
orchid index directory ./knowledge/ --namespace kb --strategy headered

# Hierarchical: parent-child chunk hierarchy
orchid index directory ./manuals/ --namespace manuals --strategy hierarchical
```

Chunk size and overlap are configurable per command or via defaults in `orchid.yml`:

```yaml
upload:
  chunk_size: 1000
  chunk_overlap: 200
```

## Scope

Documents are indexed with a configurable RAG scope:

```bash
# Shared knowledge (all tenants)
orchid index file faq.md --namespace support --scope shared

# Tenant-specific (default tenant)
orchid index file policy.md --namespace support --scope tenant
```

Scope maps to `OrchidRAGScope`:
- `shared` → `tenant_id="__shared__", user_id="seed"`
- `tenant` → `tenant_id="default", user_id="seed"`

## Qdrant Backend

To use Qdrant instead of ChromaDB for CLI indexing, configure `orchid.yml`:

```yaml
rag:
  vector_backend: qdrant
  qdrant_url: http://localhost:6333
  embedding_model: ollama/nomic-embed-text
```

Then index as normal — the CLI uses Qdrant transparently:

```bash
orchid index directory ./knowledge/ --namespace experts
# Stored in Qdrant, not ChromaDB
```

## Verifying Indexed Content

Check what's been indexed:

```bash
orchid index status --namespace experts
```

Output:

```
Namespace: experts
Documents: 86
Total chunks: 245
Avg chunks/doc: 2.8
Last indexed: 2025-01-15 10:30 UTC
Embedding model: ollama/nomic-embed-text (768d)
Vector backend: chromadb
```

## Re-indexing

To replace existing content:

```bash
orchid index directory ./knowledge/ \
  --namespace experts \
  --reindex
```

This deletes the namespace collection and re-indexes all files from scratch. Useful after:
- Updating knowledge files.
- Changing embedding models.
- Changing chunk size or strategy.

## The Parse-Once Pattern

The CLI follows the parse-once pattern internally. When indexing, the parser extracts text once and passes it to both the `ingest_document()` call (for RAG storage) and any diagnostic output. This avoids redundant CPU-intensive parsing.

## Error Handling

Per-file errors don't stop the indexing run:

```bash
orchid index directory ./knowledge/ --namespace experts
# Output:
#   indexed: 80 files
#   skipped: 2 files (unsupported format)
#   failed: 4 files (see log for details)
```

Failed files are logged with the error reason. The command exits with a non-zero code if any files failed, so CI/CD pipelines can detect issues.
