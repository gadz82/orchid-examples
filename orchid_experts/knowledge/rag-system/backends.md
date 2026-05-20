<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx, orchid/AGENTS.md, and codebase analysis -->

# Backends

Orchid supports pluggable vector store backends through the `OrchidVectorReader`, `OrchidVectorWriter`, and `OrchidVectorStoreAdmin` ABCs. The framework ships with a built-in Qdrant backend. The CLI adds a ChromaDB backend for zero-infra local usage.

## Backend Registry

Vector backends are registered in a global registry:

```python
from orchid_ai.rag.backends import VECTOR_BACKEND_REGISTRY

# Register a custom backend
VECTOR_BACKEND_REGISTRY["my_backend"] = MyVectorBackend
```

The registry maps backend names to factory functions that create backend instances.

## Qdrant Backend

**File:** `orchid_ai/rag/backends/qdrant.py`

The built-in Qdrant backend. Full-featured, suitable for production deployments.

### Configuration

```yaml
rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text
```

### Features

- Persistent vector storage.
- Hybrid search (dense + sparse).
- Metadata filtering.
- Multi-collection support (namespaces).
- Horizontal scaling.
- REST and gRPC APIs.

### Dimensions

The Qdrant collection is created with the embedding model's dimensions:

| Model | Dimensions |
|-------|-----------|
| `ollama/nomic-embed-text` | 768 |
| `openai/text-embedding-3-small` | 1536 |
| `gemini/gemini-embedding-001` | 3072 |

Switching models requires wiping and re-indexing the collection.

### Docker Setup

```yaml
# docker-compose.yml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

volumes:
  qdrant_data:
```

### Collection Management

Each RAG namespace maps to a Qdrant collection. Collections are created automatically on first ingestion:

```python
from orchid_ai.rag.factory import build_reader

reader = build_reader(
    vector_backend="qdrant",
    qdrant_url="http://localhost:6333",
    embedding_model="ollama/nomic-embed-text",
)
# Collections are created on first ingest_document() call
```

## ChromaDB Backend

**File:** `orchid_cli/rag/backends/chroma.py`

The ChromaDB backend, available in the CLI package. Suitable for zero-infra local usage.

### Configuration

```yaml
rag:
  vector_backend: chromadb
  chromadb_path: ~/.orchid/chromadb
  embedding_model: ollama/nomic-embed-text
```

### Features

- Zero-infra (no Docker required).
- Persistent storage via `PersistentClient`.
- In-memory mode for tests.
- Automatic collection creation.

### When to Use

- Local development without Docker.
- CLI usage (the CLI defaults to ChromaDB).
- Demos and prototypes.
- Single-user deployments.

### When NOT to Use

- Multi-replica deployments (ChromaDB doesn't support horizontal scaling).
- Production deployments requiring high availability.
- Deployments requiring hybrid search.

## Building a Reader

The `build_reader()` factory creates a reader from configuration:

```python
from orchid_ai.rag.factory import build_reader

reader = build_reader(
    vector_backend="qdrant",
    qdrant_url="http://localhost:6333",
    embedding_model="ollama/nomic-embed-text",
)
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `vector_backend` | Backend name (`qdrant`, `chromadb`, or custom). |
| `qdrant_url` | Qdrant server URL (for Qdrant backend). |
| `chromadb_path` | ChromaDB persistent path (for ChromaDB backend). |
| `embedding_model` | Embedding model string. |

## NullVectorReader

When no vector backend is configured, a `NullVectorReader` is used. It returns empty results for all retrieval calls. This is useful for:

- Agents that don't use RAG.
- Tests without vector store setup.
- Deployments that only use tools.

```python
runtime = OrchidRuntime(default_model="ollama/llama3.2")
# reader is None → NullVectorReader is used
```

## Custom Backends

To implement a custom vector backend:

1. Implement `OrchidVectorReader`, `OrchidVectorWriter`, and `OrchidVectorStoreAdmin`.
2. Register it with the backend registry.
3. Configure it in `orchid.yml`.

```python
from orchid_ai.rag.backends import register_vector_backend

class MyVectorBackend(OrchidVectorReader, OrchidVectorWriter, OrchidVectorStoreAdmin):
    # Implement all abstract methods
    ...

register_vector_backend("my_backend", MyVectorBackend)
```

```yaml
rag:
  vector_backend: my_backend
  my_backend_url: http://my-backend:8080
  embedding_model: ollama/nomic-embed-text
```

## Backend Selection Guide

| Backend | Infrastructure | Scaling | Hybrid Search | Best For |
|---------|---------------|---------|---------------|----------|
| Qdrant | Docker required | Horizontal | Yes | Production |
| ChromaDB | None | Single-node | No | Local dev / CLI |
| Custom | Depends | Depends | Depends | Specialized needs |
