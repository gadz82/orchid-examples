<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx, orchid/AGENTS.md, and codebase analysis -->

# Dynamic Injection

Dynamic injection is a feature that allows tool results to be stored in the vector store for future RAG retrieval. This creates a cache: on subsequent queries, the framework can retrieve the cached result from RAG instead of re-calling the tool.

## How It Works

### Step 1: Tool Execution

When a tool is called with `inject_to_rag: true`, its return value is processed for storage:

```yaml
tools:
  get_catalog:
    handler: myapp.tools.get_catalog
    description: "Get the current product catalog"
    inject_to_rag: true
    rag_ttl: 3600  # Cache for 1 hour
```

### Step 2: Storage in Vector Store

The tool result is:

1. Converted to text (if not already a string).
2. Embedded using the configured embedding model.
3. Stored in the agent's RAG namespace with metadata that includes a timestamp.

### Step 3: Retrieval on Future Queries

On subsequent queries within the same chat scope:

1. The agent checks if cached tool results exist in the vector store.
2. If cached results are newer than `rag_ttl` seconds ago, they are retrieved.
3. The cached results are merged with the RAG context from the normal retrieval step.
4. The tool is not re-called — the cached result is used instead.

## Configuration

### Per-Tool Configuration

```yaml
tools:
  expensive_api_call:
    handler: myapp.tools.expensive_call
    inject_to_rag: true
    rag_ttl: 3600  # Cache for 1 hour
```

- **`inject_to_rag`** — Store tool results in vector store. Default: `false`.
- **`rag_ttl`** — Cache TTL in seconds. Default: `null` (uses agent's `rag.rag_ttl`). Set to `0` to disable caching.

### Per-Agent Default

```yaml
agents:
  my-agent:
    rag:
      namespace: my-namespace
      rag_ttl: 3600  # Default TTL for all tools with inject_to_rag
```

### Global Default

```yaml
defaults:
  rag:
    rag_ttl: 0  # Default: caching disabled
```

## TTL Behavior

| TTL Value | Behavior |
|-----------|----------|
| `0` | Caching disabled. Tool is always called fresh. |
| `null` | Uses the agent's `rag.rag_ttl`. |
| Positive integer | Cache expires after N seconds. |

### Example TTL Scenarios

- **Exchange rates:** `rag_ttl: 300` (5 minutes — data changes frequently).
- **Product catalog:** `rag_ttl: 86400` (24 hours — data changes daily).
- **Documentation:** `rag_ttl: 604800` (7 days — data changes weekly).
- **Static reference data:** `rag_ttl: 0` (never cache — always call fresh for accuracy).

## Scope for Cached Results

Cached tool results are stored with the current chat scope:

```python
scope = OrchidRAGScope(
    tenant_id=auth.tenant_key,
    user_id=auth.user_id,
    chat_id=state.get("chat_id", ""),
    agent_id=self.name,
)
```

This means:

- Cached results are only visible within the same chat session.
- Different chat sessions don't share cached tool results.
- The cache is per-user, per-chat, per-agent.

## When to Use Dynamic Injection

- **Expensive API calls** — Tools that call external APIs with rate limits or costs.
- **Large data sets** — Tools that return large amounts of data (e.g., catalog snapshots).
- **Slow computations** — Tools that take significant time to compute results.
- **Stable data** — Tools whose results don't change frequently.

## When NOT to Use Dynamic Injection

- **Real-time data** — Tools that return data that changes every second (e.g., stock prices).
- **User-specific actions** — Tools that perform side effects (e.g., sending an email).
- **Small, fast results** — Tools that return a single value quickly (caching overhead isn't worth it).
- **Security-sensitive data** — Tools that return sensitive data that shouldn't be stored.

## Implementation Details

### Storage Format

Tool results are stored as documents with the following metadata:

| Field | Description |
|-------|-------------|
| `source` | Tool name (e.g., `get_catalog`). |
| `tool_result` | `true` (marks this as a tool result, not a document chunk). |
| `timestamp` | ISO timestamp when the result was cached. |
| `tenant_id` | Tenant identifier from scope. |
| `user_id` | User identifier from scope. |
| `chat_id` | Chat identifier from scope. |
| `agent_id` | Agent identifier from scope. |
| `namespace` | Vector store namespace. |

### Retrieval Logic

During step 5 of the GenericAgent pipeline (Dynamic RAG Injection):

1. The agent queries the vector store for tool results in the current scope.
2. Filters by `tool_result: true` and `timestamp > (now - rag_ttl)`.
3. Merges cached results with the RAG context from step 1.
4. The combined context is passed to the LLM for summarization.

### Cache Invalidation

Cached results are automatically invalidated when:

- The TTL expires.
- The chat session is deleted.
- The vector store collection is deleted.

There is no manual cache invalidation API — the TTL mechanism handles it automatically.
