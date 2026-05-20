<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx and codebase analysis -->

# Hybrid Search

Hybrid search combines dense vector similarity search with sparse keyword search to achieve better retrieval quality than either approach alone. Orchid supports hybrid search through the Qdrant backend.

## Dense vs. Sparse Search

### Dense Search (Vector Similarity)

- Embeds queries and documents into dense vectors.
- Uses cosine similarity to find semantically similar documents.
- Good at matching meaning, not exact words.
- May miss documents that use different terminology for the same concept.

### Sparse Search (Keyword Matching)

- Uses term frequency-inverse document frequency (TF-IDF) or BM25 scoring.
- Matches exact keywords in the query with keywords in the documents.
- Good at finding documents with specific terms.
- May miss documents that use synonyms or related concepts.

### Hybrid Search

Combines both approaches using Reciprocal Rank Fusion (RRF):

1. Perform dense vector search → get ranked list A.
2. Perform sparse keyword search → get ranked list B.
3. Combine rankings using RRF → get fused ranked list C.
4. Return top `k` results from the fused list.

## Reciprocal Rank Fusion (RRF)

RRF is a method for combining multiple ranked lists into a single list. For each document, it computes:

```
RRF_score = sum(1 / (k + rank_i) for each list i)
```

Where `k` is a constant (typically 60) and `rank_i` is the document's rank in list `i`.

### Why RRF Works

- Documents that rank highly in both lists get the highest combined score.
- Documents that rank highly in one list but not the other still get a moderate score.
- Documents that don't appear in either list get no score.

This produces a balanced result that benefits from both dense and sparse search.

## BM25 and SPLADE

### BM25

BM25 (Best Matching 25) is a ranking function used by search engines to estimate the relevance of documents to a given search query. It considers:

- **Term frequency** — How often the query terms appear in the document.
- **Inverse document frequency** — How rare the query terms are across the corpus.
- **Document length normalization** — Shorter documents are favored when terms match.

### SPLADE

SPLADE (Sparse Lexical and Expansion) is a neural sparse retrieval model that:

- Uses a transformer model to expand queries with related terms.
- Produces sparse vectors that can be used for keyword matching.
- Combines the benefits of neural representations with keyword matching.

SPLADE is more expensive than BM25 but can capture semantic relationships between terms that BM25 misses.

## Configuration

Hybrid search is enabled by setting the retrieval strategy to `hybrid`:

```yaml
rag:
  retrieval_strategy: hybrid
```

### Qdrant Configuration

Qdrant must be configured to support sparse vectors:

```yaml
rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text
```

The Qdrant backend automatically configures sparse vector support when hybrid search is enabled.

## When to Use Hybrid Search

- **Mixed query types** — Some queries are better served by semantic matching, others by keyword matching.
- **Technical documentation** — Users may search by exact function names (keyword) or by concept (semantic).
- **Product catalogs** — Users may search by product name (keyword) or by description (semantic).
- **Best overall quality** — When you want the best retrieval quality and can afford the extra cost.

## When NOT to Use Hybrid Search

- **Simple corpora** — If your corpus is small and well-structured, simple retrieval may be sufficient.
- **Latency-sensitive** — Hybrid search requires two searches + fusion, which adds latency.
- **Non-Qdrant backends** — Hybrid search requires a backend that supports sparse vectors (Qdrant).

## Performance Considerations

### Latency

Hybrid search adds latency compared to simple search:

- Dense search: ~50ms (depends on corpus size).
- Sparse search: ~30ms (depends on corpus size).
- RRF fusion: ~5ms.
- Total: ~85ms (vs. ~50ms for simple search).

### Storage

Hybrid search requires storing both dense and sparse vectors:

- Dense vectors: 768–3072 dimensions (depending on embedding model).
- Sparse vectors: Variable dimensions (depends on vocabulary size).

This increases storage requirements by approximately 30–50%.

### Indexing

Indexing for hybrid search takes longer because:

- Both dense and sparse embeddings must be computed.
- Both vector indexes must be built.

For large corpora, plan for 1.5–2x the indexing time of simple search.

## Hybrid Search vs. Query Transformers

Hybrid search and query transformers are complementary:

```yaml
rag:
  retrieval_strategy: hybrid
  query_transformer: reformulate
```

This configuration:

1. Reformulates the query for better retrieval.
2. Performs hybrid (dense + sparse) search on the reformulated query.
3. Combines results using RRF fusion.

This is the recommended configuration for best overall retrieval quality.
