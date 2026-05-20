<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid-website/src/content/concepts/rag.mdx, and codebase analysis -->

# RAG Best Practices

This document covers best practices for designing, configuring, and operating the RAG system in production Orchid deployments.

## Scope Design

### Use the Hierarchy Intentionally

The 5-level scope hierarchy (root → tenant → user → chat → agent) is powerful but requires careful design:

- **Root level (`__shared__`)** — For truly global knowledge (e.g., framework documentation, product manuals).
- **Tenant level** — For organization-specific knowledge (e.g., company policies, internal docs).
- **User level** — For personal knowledge (e.g., user preferences, personal notes).
- **Chat level** — For conversation-specific knowledge (e.g., uploaded documents).
- **Agent level** — For agent-specific knowledge (e.g., tool results, agent context).

### Don't Over-Scope

If a document is relevant to all users in a tenant, index it at the tenant level, not per-user. This reduces storage and ensures consistent retrieval across users.

### Use Empty Strings for Unused Levels

```python
# Tenant-level scope (not per-user, per-chat, or per-agent)
scope = OrchidRAGScope(
    tenant_id="my-tenant",
    user_id="seed",
    chat_id="",
    agent_id="",
)
```

## Embedding Model Selection

### Match Dimensions to Your Backend

Ensure the embedding model's dimensions match your vector store collection:

| Model | Dimensions | Backend Support |
|-------|-----------|-----------------|
| `ollama/nomic-embed-text` | 768 | Qdrant, ChromaDB |
| `openai/text-embedding-3-small` | 1536 | Qdrant |
| `gemini/gemini-embedding-001` | 3072 | Qdrant |

### Consider Cost vs. Quality

- **768 dimensions** — Good for most use cases. Lower cost, faster search.
- **1536 dimensions** — Better semantic understanding. Higher cost, slower search.
- **3072 dimensions** — Best quality for fine-grained distinction. Highest cost.

### Don't Switch Models Without Re-Indexing

Switching embedding models requires wiping and re-indexing the vector store. Plan for downtime or use a parallel collection during migration.

## Ingestion Strategy Selection

### Default to RecursiveIngestion

For most use cases, `RecursiveIngestion` with default settings (1000 chars / 200 overlap) works well. It produces natural chunk boundaries that respect document structure.

### Use HeaderedIngestion for Markdown

If your documents are markdown with clear heading structure, `HeaderedIngestion` produces chunks that align with document sections.

### Use SemanticIngestion for Topic-Shift Detection

If your documents have topic shifts that don't align with paragraph boundaries, `SemanticIngestion` detects semantic boundaries automatically.

## Retrieval Strategy Selection

### Start with Simple Retrieval

Begin with `simple` retrieval and measure quality. If results are insufficient, try more advanced strategies:

1. **`simple`** — Baseline.
2. **`hybrid`** — Best overall quality (if using Qdrant).
3. **`multi_query`** — Broader coverage for varied terminology.
4. **`hyde`** — Question-answer matching.
5. **`graph_rag`** — Multi-hop queries.

### Use Query Transformers

Combine retrieval strategies with query transformers for best results:

```yaml
rag:
  retrieval_strategy: hybrid
  query_transformer: reformulate
```

## k Value Tuning

### Start with k=5

The default `k=5` is a good starting point. Tune based on:

- **Corpus size** — Larger corpora may benefit from higher `k`.
- **Query type** — Broad queries may need higher `k`; specific queries may need lower `k`.
- **LLM context window** — Higher `k` consumes more tokens.

### Don't Set k Too High

Setting `k` too high (e.g., 20+) can:

- Include irrelevant chunks that dilute the context.
- Exceed the LLM context window.
- Increase latency and cost.

### Don't Set k Too Low

Setting `k` too low (e.g., 1–2) can:

- Miss relevant documents.
- Provide insufficient context for the LLM.

## Namespace Design

### One Namespace Per Domain

Use separate namespaces for different knowledge domains:

```
knowledge/
├── orchid-framework/    → namespace: orchid-framework
├── rag-system/          → namespace: rag-system
├── tools-skills/        → namespace: tools-skills
└── ...
```

This allows agents to query only their relevant domain.

### Don't Mix Unrelated Documents

Don't index unrelated documents in the same namespace. This dilutes retrieval quality and makes it harder to tune `k` values.

### Use Consistent Naming

Use lowercase, hyphenated namespace names (e.g., `orchid-framework`, not `OrchidFramework` or `orchid_framework`).

## Anti-Patterns

### Don't Pass Raw tenant_id Filters

Always use `OrchidRAGScope` — never construct raw filter dictionaries.

### Don't Parse Documents Twice

Use the parse-once pattern: call `extract_text()` once, pass the result to both the prompt builder and `ingest_document(pre_extracted_text=...)`.

### Don't Ignore TTL for Dynamic Injection

If you use `inject_to_rag: true`, set an appropriate `rag_ttl`. Without TTL, stale tool results may be used indefinitely.

### Don't Use the Wrong Embedding Model for Your Backend

Ensure the embedding model's dimensions match your vector store collection. Mismatched dimensions cause errors.

### Don't Forget to Handle Null Reader

The vector backend can be `null` in tests or deployments without RAG. Always check if `self._reader` is `None`.

## Monitoring

### Track Retrieval Quality

Monitor:

- **Hit rate** — Percentage of queries that return relevant documents.
- **Empty results** — Percentage of queries that return no documents.
- **Latency** — Time from query to retrieved documents.

### Track Ingestion Health

Monitor:

- **Ingestion errors** — Failed document ingestions.
- **Chunk count** — Number of chunks per document (should be consistent).
- **Namespace sizes** — Number of documents per namespace.

### Set Up Alerts

Alert on:

- High empty result rate (>20%).
- High ingestion error rate (>5%).
- Sudden changes in namespace sizes.
