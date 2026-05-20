<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid-website/src/content/concepts/rag.mdx, and codebase analysis -->

# RAG Scope Design

Production guidelines for designing the 5-level RAG scope hierarchy.

## Multi-Tenancy Patterns

### Pattern 1: Fully Isolated Tenants

Each tenant has completely separate RAG data:

```python
# Tenant A
scope = OrchidRAGScope(tenant_id="tenant-a", user_id="seed", chat_id="", agent_id="")

# Tenant B
scope = OrchidRAGScope(tenant_id="tenant-b", user_id="seed", chat_id="", agent_id="")
```

### Pattern 2: Shared + Tenant Knowledge

Combine shared knowledge with tenant-specific data:

```python
# Shared knowledge (accessible to all tenants)
shared_scope = OrchidRAGScope(tenant_id="__shared__", user_id="seed", chat_id="", agent_id="")

# Tenant-specific knowledge
tenant_scope = OrchidRAGScope(tenant_id="tenant-a", user_id="seed", chat_id="", agent_id="")
```

### Pattern 3: Full Hierarchy

Utilize all 5 levels:

```python
# Company-wide policies (tenant level)
policy_scope = OrchidRAGScope(tenant_id="acme", user_id="seed", chat_id="", agent_id="")

# User's personal notes (user level)
user_scope = OrchidRAGScope(tenant_id="acme", user_id="user-123", chat_id="", agent_id="")

# Conversation-specific docs (chat level)
chat_scope = OrchidRAGScope(tenant_id="acme", user_id="user-123", chat_id="chat-456", agent_id="")
```

## Scope Design Principles

### 1. Least Privilege

Index documents at the most restrictive level possible:
- If a document is user-specific, don't index at tenant level.
- If a document is conversation-specific, don't index at user level.

### 2. Consistent Seed User

Use `user_id="seed"` for system-indexed documents:

```python
scope = OrchidRAGScope(tenant_id="acme", user_id="seed", chat_id="", agent_id="")
```

This distinguishes system-indexed content from user-generated content.

### 3. Namespace per Domain

Use separate namespaces for different knowledge domains:

```python
namespace="product-docs"   # Product documentation
namespace="support-faq"     # Support FAQ
namespace="internal-policies"  # Internal policies
```

### 4. Agent-Level for Tool Results

Tool results with `inject_to_rag: true` are stored at the agent level:

```python
scope = OrchidRAGScope(
    tenant_id=auth.tenant_key,
    user_id=auth.user_id,
    chat_id=chat_id,
    agent_id=self.name,  # Scoped to the calling agent
)
```

## Performance Considerations

- **Too many scopes** — Each scope level adds filter complexity. Use only necessary levels.
- **Empty strings** — Use `""` for unused levels, not `null` or `"*"`.
- **Qdrant filters** — Qdrant's payload filtering is efficient for scope-based queries.
- **Index fields** — Qdrant indexes payload fields used in scope filtering for performance.

## Common Mistakes

- **Using `"*"` for all users** — Security risk. Use `"__shared__"` for truly shared content.
- **Forgetting chat_id** — Uploads within a chat should be scoped to that chat.
- **Mixing namespaces** — Don't index unrelated content in the same namespace.
