<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid/AGENTS.md, and codebase analysis -->

# Embedding Model Choice

Guidelines for selecting and managing embedding models in production.

## Model Comparison

| Model | Dimensions | Cost | Quality | Best For |
|-------|-----------|------|---------|----------|
| `ollama/nomic-embed-text` | 768 | Free (local) | Good | Local dev, privacy |
| `openai/text-embedding-3-small` | 1536 | Low ($0.02/1M tokens) | Very Good | General production |
| `openai/text-embedding-3-large` | 3072 | Medium ($0.13/1M tokens) | Excellent | High-accuracy needs |
| `gemini/gemini-embedding-001` | 3072 | Low | Very Good | Gemini ecosystem |

## Dimension Matching

The embedding model's dimensions **must match** the vector store collection:

```yaml
rag:
  vector_backend: qdrant
  embedding_model: ollama/nomic-embed-text  # 768 dimensions
  # Qdrant collection is created with 768 dimensions
```

### Switching Models

Switching requires re-indexing:

1. Stop the API.
2. Delete Qdrant collections.
3. Update `embedding_model` in `orchid.yml`.
4. Restart and re-index all documents.

### Migration Strategy

For production, use parallel collections:

1. Create a new collection with the new model's dimensions.
2. Index documents into the new collection (while old is still serving).
3. Switch the `embedding_model` config.
4. Delete the old collection.

## Cost Analysis

| Model | Cost per 1M tokens | Cost per 1000 chunks (500 chars each) | Annual (1M searches) |
|-------|-------------------|--------------------------------------|---------------------|
| Ollama nomic-embed-text | $0 (local) | $0 | $0 (electricity only) |
| text-embedding-3-small | ~$0.02 | ~$0.01 | ~$20 |
| text-embedding-3-large | ~$0.13 | ~$0.05 | ~$130 |
| Gemini embedding-001 | ~$0.01 | ~$0.005 | ~$10 |

## Performance

| Model | Latency (per batch) | Throughput |
|-------|---------------------|------------|
| Ollama nomic-embed-text | ~50ms (GPU) / ~200ms (CPU) | Depends on hardware |
| text-embedding-3-small | ~100ms (API) | 3000 RPM (OpenAI tier 1) |
| text-embedding-3-large | ~150ms (API) | 3000 RPM (OpenAI tier 1) |
| Gemini embedding-001 | ~80ms (API) | 1500 RPM |

## Best Practices

- Use Ollama for development (free, no API keys).
- Use text-embedding-3-small for most production use cases (good balance of cost/quality).
- Use text-embedding-3-large for fine-grained semantic matching (legal, medical).
- Plan for re-indexing when switching models.
- Store the embedding model name in document metadata for audits.
