<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx, orchid-website/src/content/examples/rag-strategies.mdx, and codebase analysis -->

# Retrieval Strategies

Retrieval strategies control how the vector store is queried to find relevant documents for a given user query. Orchid provides multiple strategies, each with different trade-offs in accuracy, latency, and token usage.

## Simple Retrieval

The default strategy. Embeds the user query and performs a single cosine similarity search.

### How It Works

1. Embed the user query using the configured embedding model.
2. Perform a cosine similarity search in the vector store.
3. Return the top `k` most similar chunks.

### Configuration

```yaml
rag:
  retrieval_strategy: simple
```

### When to Use

- Most use cases.
- When queries are clear and specific.
- When latency is a priority.

### Trade-offs

- Fastest strategy (single embedding + single search).
- May miss relevant documents if the query uses different terminology than the documents.

## Multi-Query Retrieval

Generates multiple variations of the user query and retrieves documents for each, then deduplicates.

### How It Works

1. Use an LLM to generate N variations of the user query (different phrasings, synonyms).
2. Embed each variation.
3. Perform a similarity search for each variation.
4. Deduplicate and rank results across all queries.
5. Return the top `k` unique chunks.

### Configuration

```yaml
rag:
  retrieval_strategy: multi_query
  multi_query_count: 3
```

### When to Use

- When users may phrase queries differently than the documents.
- When you want broader coverage of the knowledge base.
- When the corpus uses varied terminology.

### Trade-offs

- More expensive (N+1 embeddings + N searches).
- Broader coverage.
- May return more diverse results.

## HyDE Retrieval (Hypothetical Document Embeddings)

Generates a hypothetical answer to the query, then uses that answer's embedding to find similar documents.

### How It Works

1. Use an LLM to generate a hypothetical answer to the user query.
2. Embed the hypothetical answer.
3. Perform a similarity search using the hypothetical answer's embedding.
4. Return the top `k` most similar chunks.

### Configuration

```yaml
rag:
  retrieval_strategy: hyde
```

### When to Use

- When queries are questions and documents contain answers.
- When the query is too short to match well with documents.
- When you want to match on answer content rather than query content.

### Trade-offs

- More expensive (LLM call + embedding + search).
- Can find documents that simple retrieval misses.
- The hypothetical answer may introduce bias.

## Hybrid Retrieval

Combines dense (vector) search with sparse (keyword) search using RRF (Reciprocal Rank Fusion).

### How It Works

1. Perform a dense vector similarity search.
2. Perform a sparse keyword search (BM25 or SPLADE).
3. Combine results using RRF fusion.
4. Return the top `k` fused results.

### Configuration

```yaml
rag:
  retrieval_strategy: hybrid
```

### When to Use

- When you need both semantic and keyword matching.
- When some queries are better served by exact keyword matches.
- When you want the best of both dense and sparse search.

### Trade-offs

- More expensive (two searches + fusion).
- Best overall retrieval quality.
- Requires a vector backend that supports hybrid search (Qdrant).

## GraphRAG Retrieval

Uses a knowledge graph to enhance retrieval by following relationships between entities.

### How It Works

1. Extract entities and relationships from documents during ingestion.
2. Store the graph alongside the vector embeddings.
3. At retrieval time, find matching entities and traverse the graph to find related documents.
4. Combine graph-based results with vector-based results.

### Configuration

```yaml
rag:
  retrieval_strategy: graph_rag
```

### When to Use

- When documents have explicit relationships (e.g., product catalog with categories).
- When you need to answer multi-hop questions.
- When the knowledge base has a clear entity structure.

### Trade-offs

- Most expensive (graph construction + traversal + vector search).
- Best for complex, multi-hop queries.
- Requires graph-capable vector backend.

## Query Transformers

Retrieval strategies can be combined with query transformers that preprocess the query before retrieval:

| Transformer | Purpose |
|-------------|---------|
| `reformulate` | Rewrites the query for better retrieval. |
| `decompose` | Splits a complex query into sub-queries. |
| `multi_query` | Generates multiple query variations. |
| `hyde` | Generates a hypothetical answer for embedding. |

These are configured separately from the retrieval strategy and can be combined:

```yaml
rag:
  retrieval_strategy: simple
  query_transformer: reformulate
```

## Strategy Selection Guide

| Strategy | Latency | Accuracy | Cost |
|----------|---------|----------|------|
| `simple` | Low | Good | Low |
| `multi_query` | Medium | Better | Medium |
| `hyde` | Medium | Better | Medium |
| `hybrid` | Medium | Best | Medium |
| `graph_rag` | High | Best (multi-hop) | High |

## Custom Retrieval Strategies

To add a custom retrieval strategy:

1. Subclass the retrieval strategy base class.
2. Implement the `retrieve()` method.
3. Register it with the strategy registry.

```python
from orchid_ai.rag.retrieval import register_retrieval_strategy

class MyRetrievalStrategy:
    async def retrieve(self, query, scope, k, reader):
        # Custom retrieval logic
        return documents

register_retrieval_strategy("my_strategy", MyRetrievalStrategy)
```
