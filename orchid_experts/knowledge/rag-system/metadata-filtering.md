<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx and codebase analysis -->

# Metadata Filtering

Metadata filtering allows you to narrow retrieval results by applying structured filters on document metadata, in addition to vector similarity. This is useful when you need to restrict retrieval to specific document types, date ranges, or other structured attributes.

## Filter Mini-Language

Orchid uses a filter mini-language that supports common comparison operators:

### Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `{"source": "manual.pdf"}` |
| `!=` | Not equal | `{"source": {"$ne": "manual.pdf"}}` |
| `>` | Greater than | `{"date": {"$gt": "2024-01-01"}}` |
| `>=` | Greater than or equal | `{"date": {"$gte": "2024-01-01"}}` |
| `<` | Less than | `{"date": {"$lt": "2024-01-01"}}` |
| `<=` | Less than or equal | `{"date": {"$lte": "2024-01-01"}}` |
| `in` | In list | `{"source": {"$in": ["a.md", "b.md"]}}` |
| `not_in` | Not in list | `{"source": {"$nin": ["a.md", "b.md"]}}` |

### Combining Filters

Filters can be combined with logical operators:

```python
{
    "$and": [
        {"source": {"$in": ["a.md", "b.md"]}},
        {"date": {"$gte": "2024-01-01"}},
    ]
}
```

```python
{
    "$or": [
        {"source": "a.md"},
        {"source": "b.md"},
    ]
}
```

## Static vs. Dynamic Filters

### Static Filters

Static filters are defined in the agent's RAG configuration and apply to every retrieval:

```yaml
agents:
  my-agent:
    rag:
      namespace: my-namespace
      k: 5
      filters:
        source: "manual.pdf"
```

Every time this agent retrieves documents, it only returns chunks from `manual.pdf`.

### Dynamic Filters

Dynamic filters are computed at runtime based on the query, auth context, or other state. They are passed to the retrieval call:

```python
filters = {
    "tenant_id": auth.tenant_key,
    "document_type": "technical",
}

docs = await self.reader.retrieve(
    query=user_query,
    scope=scope,
    k=5,
    filters=filters,
)
```

Dynamic filters are useful for:

- Tenant-level filtering (beyond the scope hierarchy).
- Document type filtering based on user preferences.
- Date range filtering based on query context.

## Scope vs. Filters

The `OrchidRAGScope` and metadata filters serve different purposes:

- **Scope** — Hierarchical access control (root → tenant → user → chat → agent). Determines which documents are *visible* to the agent.
- **Filters** — Structured attribute matching. Determines which visible documents are *relevant* based on metadata.

They are used together:

```python
docs = await self.reader.retrieve(
    query=user_query,
    scope=OrchidRAGScope(
        tenant_id="my-tenant",
        user_id="user-123",
        chat_id="",
        agent_id="my-agent",
    ),
    k=5,
    filters={"document_type": "technical"},
)
```

The scope ensures the agent only sees documents within its hierarchy. The filter further restricts results to technical documents.

## Common Metadata Fields

Documents ingested through the pipeline carry standard metadata:

| Field | Description |
|-------|-------------|
| `source` | Original file name. |
| `namespace` | Vector store namespace. |
| `tenant_id` | Tenant identifier from scope. |
| `user_id` | User identifier from scope. |
| `chat_id` | Chat identifier from scope. |
| `agent_id` | Agent identifier from scope. |
| `chunk_index` | Position of the chunk within the document. |
| `total_chunks` | Total number of chunks in the document. |

Custom metadata can be added during ingestion:

```python
await ingest_document(
    file_bytes=content.encode("utf-8"),
    filename="doc.md",
    scope=scope,
    namespace="knowledge",
    writer=reader,
    ingestion=strategy,
    pre_extracted_text=content,
    metadata={"document_type": "technical", "version": "2.0"},
)
```

## Filter Performance

Metadata filters are applied *after* the vector similarity search in most backends. This means:

1. The vector search returns the top `k` results.
2. The filter is applied to those results.
3. If the filter eliminates some results, fewer than `k` documents may be returned.

To ensure you get `k` results after filtering, some backends support pre-filtering (applying the filter during the vector search). Check your backend's documentation for support.

## When to Use Filters

- **Document type filtering** — Restrict retrieval to specific document types (e.g., only API docs, not tutorials).
- **Date range filtering** — Only retrieve documents from a specific time period.
- **Source filtering** — Only retrieve from specific files or sources.
- **Version filtering** — Only retrieve documents from a specific version.
- **Language filtering** — Only retrieve documents in a specific language.

## When NOT to Use Filters

- **When the scope hierarchy is sufficient** — If you only need tenant/user/chat-level filtering, use scope instead of filters.
- **When the corpus is small** — Filters add complexity. If you have a small corpus, simple retrieval may be sufficient.
- **When filters are too restrictive** — Over-filtering can eliminate relevant documents. Test your filters to ensure they don't block legitimate results.
