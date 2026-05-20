<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/agents.mdx, and codebase analysis -->

# Per-Tool RAG Overrides

Per-tool RAG overrides allow individual tools to customize their RAG ingestion and retrieval settings, independent of the agent's default RAG configuration. This is useful when different tools have different caching and retrieval requirements.

## Ingestion Override

Tools can override the ingestion strategy used when their results are stored in RAG:

```yaml
tools:
  get_catalog:
    handler: myapp.tools.catalog.get_catalog
    description: "Get the product catalog"
    inject_to_rag: true
    rag:
      ingestion_strategy: recursive
      chunk_size: 2000
      chunk_overlap: 400
```

### Fields

- **`ingestion_strategy`** — The ingestion strategy to use (`recursive`, `semantic`, `hierarchical`, `headered`). Default: agent's strategy.
- **`chunk_size`** — Target chunk size in characters. Default: agent's chunk size.
- **`chunk_overlap`** — Overlap between chunks in characters. Default: agent's chunk overlap.

### When to Use

- **Large tool results** — Use larger chunk sizes for tools that return large amounts of data.
- **Structured tool results** — Use `headered` ingestion for tools that return markdown-formatted results.
- **Semantic tool results** — Use `semantic` ingestion for tools that return text with topic shifts.

## Retrieval Override

Tools can override the retrieval strategy used when their cached results are retrieved:

```yaml
tools:
  get_catalog:
    handler: myapp.tools.catalog.get_catalog
    description: "Get the product catalog"
    inject_to_rag: true
    rag:
      retrieval_strategy: simple
      k: 10
```

### Fields

- **`retrieval_strategy`** — The retrieval strategy to use (`simple`, `multi_query`, `hyde`, `hybrid`, `graph_rag`). Default: agent's strategy.
- **`k`** — Number of documents to retrieve. Default: agent's `k`.

### When to Use

- **Precise tool results** — Use `simple` retrieval with a low `k` for tools with precise, focused results.
- **Broad tool results** — Use `hybrid` retrieval with a higher `k` for tools with broad, varied results.

## TTL Override

Tools can override the RAG cache TTL:

```yaml
tools:
  get_exchange_rate:
    handler: myapp.tools.finance.get_exchange_rate
    description: "Get current exchange rate"
    inject_to_rag: true
    rag_ttl: 300  # 5 minutes

  get_product_catalog:
    handler: myapp.tools.catalog.get_catalog
    description: "Get the product catalog"
    inject_to_rag: true
    rag_ttl: 86400  # 24 hours
```

### TTL Hierarchy

| Level | Field | Priority |
|-------|-------|----------|
| Tool | `tools.<name>.rag_ttl` | Highest |
| Agent | `agents.<name>.rag.rag_ttl` | Medium |
| Default | `defaults.rag.rag_ttl` | Lowest |

The tool-level `rag_ttl` overrides the agent-level, which overrides the default.

## Complete Example

```yaml
defaults:
  rag:
    rag_ttl: 0  # Default: caching disabled

agents:
  shopping-assistant:
    description: "Shopping assistant"
    rag:
      namespace: shopping
      k: 5
      rag_ttl: 3600  # 1 hour default for this agent

tools:
  get_catalog:
    handler: myapp.tools.catalog.get_catalog
    description: "Get the product catalog"
    inject_to_rag: true
    rag_ttl: 86400  # 24 hours (overrides agent default)
    rag:
      ingestion_strategy: recursive
      chunk_size: 2000
      chunk_overlap: 400
      retrieval_strategy: hybrid
      k: 10

  get_exchange_rate:
    handler: myapp.tools.finance.get_exchange_rate
    description: "Get current exchange rate"
    inject_to_rag: true
    rag_ttl: 300  # 5 minutes (overrides agent default)
```

In this example:

- `get_catalog` caches for 24 hours with larger chunks and hybrid retrieval.
- `get_exchange_rate` caches for 5 minutes with default ingestion/retrieval.
- Other tools with `inject_to_rag: true` would use the agent default of 1 hour.

## When to Use Per-Tool Overrides

- **Different data freshness requirements** — Some tools need fresh data, others can cache longer.
- **Different result sizes** — Some tools return large results that need larger chunks.
- **Different retrieval needs** — Some tools benefit from hybrid retrieval, others from simple.

## When NOT to Use Per-Tool Overrides

- **When all tools have the same requirements** — Use agent-level defaults.
- **When the defaults are sufficient** — Don't add complexity unless needed.
- **When tools don't use `inject_to_rag`** — Overrides only apply to tools with `inject_to_rag: true`.
