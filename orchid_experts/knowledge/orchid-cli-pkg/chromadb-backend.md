<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# ChromaDB Backend

The CLI uses ChromaDB as its default vector store backend, enabling zero-infrastructure RAG without Docker, Kubernetes, or external services. ChromaDB runs embedded in the CLI process.

## Zero-Infra RAG

No Docker, no external services, no API keys:

```bash
orchid index directory ./knowledge/ --namespace experts
# Uses ChromaDB automatically, stored locally
```

ChromaDB persists data to `~/.orchid/chromadb/`, and the CLI's `PersistentClient` manages schema creation, indexing, and retrieval.

## Storage Layout

```
~/.orchid/
├── chromadb/
│   ├── chroma.sqlite3          # ChromaDB metadata and mapping
│   └── <uuid>/                 # One subdirectory per collection
│       └── experts/            # Namespace "experts" → collection
│           ├── data_level0.bin
│           ├── header.bin
│           ├── index_metadata.pickle
│           └── link_lists.bin
└── tokens.json                 # OAuth tokens (0o600 permissions)
```

## PersistentClient vs In-Memory

### PersistentClient (Interactive Mode)

Used for `orchid chat interactive` and `orchid index`:

```python
from chromadb import PersistentClient

client = PersistentClient(path="~/.orchid/chromadb")
collection = client.get_or_create_collection("experts")
```

Data persists across CLI restarts. Indexed knowledge is available across sessions.

### In-Memory (One-Off Commands)

Used for `orchid chat send` (single messages):

```python
client = chromadb.Client()  # Ephemeral, no persistence
```

Data is lost when the command exits. Suitable for one-off queries where you don't need persistent RAG.

## Switching to Qdrant

To use Qdrant instead of ChromaDB, configure `orchid.yml`:

```yaml
rag:
  vector_backend: qdrant
  qdrant_url: http://localhost:6333
  embedding_model: ollama/nomic-embed-text
```

The CLI detects `vector_backend: qdrant` and uses the Qdrant backend instead of the ChromaDB default. Both backends implement the same `OrchidVectorReader` / `OrchidVectorWriter` ABCs, so agent code doesn't change.

## Backend Registration

The ChromaDB backend is registered in the global `VECTOR_BACKEND_REGISTRY` at CLI startup:

```python
from orchid_ai.rag.backends import VECTOR_BACKEND_REGISTRY

VECTOR_BACKEND_REGISTRY["chromadb"] = ChromaDBBackend
```

The `build_reader()` factory uses this registry:

```python
reader = build_reader(
    vector_backend="chromadb",
    chromadb_path="~/.orchid/chromadb",
    embedding_model="ollama/nomic-embed-text",
)
```

## When to Use ChromaDB

- Local development — no Docker required.
- Single-user deployments — no concurrency concerns.
- Demos and prototypes — quick setup.
- Air-gapped environments — no network dependencies.
- CI/CD pipelines — no service dependencies.

## When NOT to Use ChromaDB

- Multi-replica deployments — ChromaDB uses file locking, doesn't support concurrent writers well.
- Production with high availability — Qdrant cluster mode is better.
- Large-scale deployments (1M+ vectors) — Qdrant scales horizontally.
- Hybrid search — ChromaDB doesn't support sparse vectors for dense+sparse fusion.
- High-throughput indexing — Qdrant's gRPC API is faster for bulk operations.

## Migrating from ChromaDB to Qdrant

1. Export ChromaDB data to a portable format.
2. Install and start Qdrant.
3. Update `orchid.yml` to `vector_backend: qdrant`.
4. Re-index documents into Qdrant.
5. Verify retrieval quality matches.

The same `embedding_model` must be used in both backends to maintain compatible vector dimensions.
