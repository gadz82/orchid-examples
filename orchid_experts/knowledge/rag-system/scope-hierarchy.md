<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx, orchid/AGENTS.md, and codebase analysis -->

# Scope Hierarchy

Orchid's RAG system uses a 5-level hierarchical scoping mechanism called `OrchidRAGScope`. This hierarchy determines which documents are visible to which agents, enabling multi-tenant RAG with fine-grained access control.

## The 5-Level Hierarchy

```
root (shared across all tenants)
  └── tenant (shared across all users in a tenant)
        └── user (private to a single user)
              └── chat (private to a single conversation)
                    └── agent (private to a single agent)
```

Each level is more restrictive than the previous. A document indexed at the `tenant` level is visible to all users in that tenant. A document indexed at the `chat` level is visible only within that specific conversation.

## OrchidRAGScope

**File:** `orchid_ai/rag/scopes.py`

```python
from orchid_ai.rag.scopes import OrchidRAGScope

scope = OrchidRAGScope(
    tenant_id="my-tenant",
    user_id="user-123",
    chat_id="chat-456",
    agent_id="my-agent",
)
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `tenant_id` | `str` | The tenant identifier. Use `"__shared__"` for cross-tenant documents. |
| `user_id` | `str` | The user identifier. Use `"seed"` for seeding shared knowledge. |
| `chat_id` | `str` | The chat session ID. Use `""` for non-chat-scoped documents. |
| `agent_id` | `str` | The agent name. Use `""` for non-agent-scoped documents. |

## How Scoping Works

### Indexing

When a document is ingested, the scope is stored as metadata alongside the embedding:

```python
await ingest_document(
    file_bytes=content.encode("utf-8"),
    filename="doc.md",
    scope=OrchidRAGScope(
        tenant_id="__shared__",
        user_id="seed",
        chat_id="",
        agent_id="",
    ),
    namespace="knowledge",
    writer=reader,
    ingestion=RecursiveIngestion(),
    pre_extracted_text=content,
)
```

The document is stored with metadata that includes the full scope hierarchy.

### Retrieval

When an agent queries the vector store, the scope is used to build a filter that matches documents at the agent's level and all parent levels:

```python
docs = await self.reader.retrieve(
    query=user_query,
    scope=OrchidRAGScope(
        tenant_id="my-tenant",
        user_id="user-123",
        chat_id="chat-456",
        agent_id="my-agent",
    ),
    k=5,
)
```

The filter matches documents where:

- `tenant_id` matches `my-tenant` OR is `"__shared__"` (root level).
- `user_id` matches `user-123` OR is `"seed"` OR is empty (tenant level).
- `chat_id` matches `chat-456` OR is empty (user level).
- `agent_id` matches `my-agent` OR is empty (chat level).

This means an agent sees:

1. Shared documents (root level).
2. Tenant-level documents.
3. User-level documents.
4. Chat-level documents.
5. Agent-level documents.

## Common Scope Patterns

### Shared Knowledge Base

Documents available to all tenants and users:

```python
scope = OrchidRAGScope(
    tenant_id="__shared__",
    user_id="seed",
    chat_id="",
    agent_id="",
)
```

Used during startup hooks to seed common knowledge.

### Tenant-Specific Knowledge

Documents available to all users within a specific tenant:

```python
scope = OrchidRAGScope(
    tenant_id="acme-corp",
    user_id="seed",
    chat_id="",
    agent_id="",
)
```

Used for company-specific documentation.

### User-Private Knowledge

Documents visible only to a specific user:

```python
scope = OrchidRAGScope(
    tenant_id="acme-corp",
    user_id="user-123",
    chat_id="",
    agent_id="",
)
```

Used for personal notes or preferences.

### Chat-Specific Knowledge

Documents visible only within a specific conversation:

```python
scope = OrchidRAGScope(
    tenant_id="acme-corp",
    user_id="user-123",
    chat_id="chat-456",
    agent_id="",
)
```

Used for uploaded documents in a chat session.

### Agent-Specific Knowledge

Documents visible only to a specific agent:

```python
scope = OrchidRAGScope(
    tenant_id="acme-corp",
    user_id="user-123",
    chat_id="chat-456",
    agent_id="my-agent",
)
```

Used for agent-specific tool results or context.

## Important Rules

### Never Pass Raw tenant_id Filters

Always use `OrchidRAGScope` — never construct raw filter dictionaries:

```python
# Correct
scope = OrchidRAGScope(tenant_id=auth.tenant_key, user_id=auth.user_id, chat_id="", agent_id="")
docs = await self.reader.retrieve(query, scope=scope, k=5)

# Incorrect
docs = await self.reader.retrieve(query, filters={"tenant_id": auth.tenant_key}, k=5)
```

### Use auth.tenant_key, Not Raw tenant_id

The `auth.tenant_key` property handles the null case (defaults to `"default"`):

```python
scope = OrchidRAGScope(
    tenant_id=auth.tenant_key,  # Handles null → "default"
    user_id=auth.user_id,
    chat_id=state.get("chat_id", ""),
    agent_id=self.name,
)
```

### Empty Strings for Unused Levels

Use empty strings (`""`) for scope levels that don't apply:

```python
# Tenant-level scope (no chat or agent specificity)
scope = OrchidRAGScope(
    tenant_id="my-tenant",
    user_id="seed",
    chat_id="",
    agent_id="",
)
```
