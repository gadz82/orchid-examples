<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, orchid-website/src/content/concepts/embeddings.mdx, and codebase analysis -->

# Embeddings

Embeddings are the foundation of Orchid's RAG system. They convert text into dense vector representations that can be compared using cosine similarity in the vector store. Orchid uses LangChain's `Embeddings` abstraction with a factory function that creates embedding models from model strings.

## Embedding Models

Orchid supports multiple embedding models through the `build_embeddings(model_string)` factory:

```python
from orchid_ai.rag.factory import build_embeddings

embeddings = build_embeddings("ollama/nomic-embed-text")
```

### Supported Models

| Model | Dimensions | Provider |
|-------|-----------|----------|
| `ollama/nomic-embed-text` | 768 | Ollama (local) |
| `openai/text-embedding-3-small` | 1536 | OpenAI |
| `openai/text-embedding-3-large` | 3072 | OpenAI |
| `gemini/gemini-embedding-001` | 3072 | Google |

### Critical: Dimension Matching

The embedding dimensions **must match** the vector store collection's dimensions. Qdrant collections are created with a fixed dimension size. If you switch embedding models, you must wipe and re-index the collection.

```yaml
rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text  # 768 dimensions
```

If you later change to `openai/text-embedding-3-small` (1536 dimensions), the existing Qdrant collection will reject the new vectors because the dimensions don't match.

### Switching Models

To switch embedding models:

1. Stop the application.
2. Delete the existing Qdrant collections (or create new ones with different names).
3. Update `embedding_model` in `orchid.yml`.
4. Re-index all documents with the new embedding model.

```bash
# Delete Qdrant collections
curl -X DELETE http://localhost:6333/collections/my_namespace

# Restart with new embedding model
# Re-run the startup hook to re-index
```

## build_embeddings() Factory

The factory works similarly to `build_chat_model()`:

1. Parses the model string to extract the provider and model name.
2. Checks if a provider-specific LangChain package is installed.
3. If available, creates the provider-specific embedding model directly.
4. Falls back to a generic implementation via `litellm`.

### Provider Priority

| Provider | Package | Fallback |
|----------|---------|----------|
| `ollama/` | `langchain-ollama` | Generic |
| `openai/` | `langchain-openai` | Generic |
| `gemini/` | `langchain-google-genai` | Generic |

## Embedding in the RAG Pipeline

Embeddings are used at two points in the RAG pipeline:

### Indexing (Write)

When a document is ingested:

1. The document text is split into chunks (by the ingestion strategy).
2. Each chunk is embedded using `build_embeddings()`.
3. The embedding + metadata is stored in the vector store.

```python
from orchid_ai.documents.pipeline import ingest_document
from orchid_ai.documents.strategies import RecursiveIngestion
from orchid_ai.rag.scopes import OrchidRAGScope

await ingest_document(
    file_bytes=content.encode("utf-8"),
    filename="doc.md",
    scope=OrchidRAGScope(tenant_id="__shared__", user_id="seed", chat_id="", agent_id=""),
    namespace="my-namespace",
    writer=reader,
    ingestion=RecursiveIngestion(),
    pre_extracted_text=content,
)
```

### Retrieval (Read)

When an agent queries the vector store:

1. The user query is embedded using the same embedding model.
2. A cosine similarity search finds the top `k` most similar chunks.
3. The matching chunks are returned as `Document` objects with their metadata.

```python
docs = await self.reader.retrieve(
    query=user_query,
    scope=rag_scope,
    k=5,
)
```

## Embedding Configuration

The embedding model is configured in `orchid.yml`:

```yaml
rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text
```

### Ollama Embedding Setup

For local Ollama embeddings, ensure the model is pulled:

```bash
ollama pull nomic-embed-text
```

And configure the API base if running in Docker:

```yaml
llm:
  ollama_api_base: http://host.docker.internal:11434
```

## Cost and Performance Considerations

### Local vs. Cloud

- **Ollama (local)** — Free, no API calls, but requires local GPU/CPU resources. Good for development and small deployments.
- **OpenAI** — Pay per token, high quality, reliable. Best for production deployments.
- **Google** — Competitive pricing, good quality. Alternative to OpenAI.

### Dimension Trade-offs

Higher dimensions generally mean better semantic understanding but:

- More storage in the vector store.
- Slower similarity searches.
- Higher embedding API costs.

For most use cases, 768 dimensions (nomic-embed-text) is sufficient. Use 1536+ dimensions when you need fine-grained semantic distinction (e.g., legal documents, technical specifications).

## Common Pitfalls

- **Mismatched dimensions** — Switching embedding models without re-indexing causes vector store errors.
- **Missing Ollama model** — Forgetting to `ollama pull nomic-embed-text` causes embedding failures.
- **Using different models for indexing and retrieval** — The same embedding model must be used for both. The factory ensures this by using the configured model for all embedding operations.
