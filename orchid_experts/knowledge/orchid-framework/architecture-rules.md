<!-- Source: derived from orchid/AGENTS.md and codebase analysis -->

# Architecture Rules

The Orchid framework enforces strict architectural rules to maintain clean separation of concerns, prevent dependency cycles, and ensure the codebase remains maintainable as it grows. These rules are non-negotiable and are enforced through code review and automated checks.

## Rule 1: core/ Has Zero External Dependencies

`orchid_ai/core/` imports only the Python standard library and `langchain-core` (for `Document` and message types). No concrete backend imports are allowed:

- **Forbidden:** `qdrant_client`, `asyncpg`, `litellm`, `aiosqlite`, `httpx`, `langchain_openai`, etc.
- **Allowed:** Python stdlib, `langchain_core` (for `Document`, `BaseChatModel`, `Embeddings`, message types).

Every other module in the framework depends on `core/` — never the reverse. Violating this is an architectural bug.

### Why This Matters

`core/` defines the abstract interfaces that the entire framework builds on. If `core/` imports concrete implementations, it creates circular dependencies and makes the framework tightly coupled to specific backends.

## Rule 2: No Qdrant Imports Outside rag/backends/

All vector store access goes through the ABCs in `core/repository.py`:

- `OrchidVectorReader` — for retrieval.
- `OrchidVectorWriter` — for indexing.
- `OrchidVectorStoreAdmin` — for collection management.

No module outside `rag/backends/` may import `qdrant_client` or any other vector store client directly.

### Why This Matters

This allows swapping vector store backends (Qdrant, ChromaDB, Pinecone, etc.) without changing agent code. Agents depend only on the abstract `OrchidVectorReader` interface.

## Rule 3: RAG Always Uses OrchidRAGScope

Never pass raw `tenant_id` filters to retrieval calls. Always use `OrchidRAGScope`:

```python
from orchid_ai.rag.scopes import OrchidRAGScope

scope = OrchidRAGScope(
    tenant_id=auth.tenant_key,
    user_id=auth.user_id,
    chat_id=state.get("chat_id", ""),
    agent_id=self.name,
)
```

The 5-level hierarchy is: root → tenant → user → chat → agent.

### Why This Matters

The scope hierarchy enables hierarchical RAG filtering, where documents at higher levels (e.g., tenant-level) are visible to all lower-level scopes (e.g., user-level). Raw filters bypass this hierarchy and break multi-tenancy.

## Rule 4: Parse-Once Pattern for Documents

Call `extract_text()` once, pass the result to both the prompt builder and `ingest_document(pre_extracted_text=...)`:

```python
content = await extract_text(file_bytes, filename)

# Use for prompt
prompt = f"Document:\n{content}\n\nQuestion: {query}"

# Use for RAG ingestion
await ingest_document(
    file_bytes=file_bytes,
    filename=filename,
    scope=scope,
    namespace=namespace,
    writer=reader,
    ingestion=strategy,
    pre_extracted_text=content,
)
```

### Why This Matters

Parsing is expensive (especially PDF and image parsing). Parsing the same file twice wastes resources and can produce inconsistent results if the parser is non-deterministic.

## Rule 5: Imports Are from orchid_ai, Not from src

All imports use `from orchid_ai.xxx`, never `from src.xxx`. The three-package split uses `orchid_ai.` as the import root.

```python
# Correct
from orchid_ai.core.agent import OrchidAgent
from orchid_ai.rag.scopes import OrchidRAGScope

# Incorrect
from src.core.agent import OrchidAgent
```

### Why This Matters

The package is distributed as `orchid-ai` on PyPI. Using `orchid_ai.` as the import root ensures consistency between development and production.

## Rule 6: No Vendor-Specific Code

Code, comments, docstrings, and examples inside `orchid/orchid_ai/` must NEVER reference any concrete product, vendor name, or domain-specific object. Platform integrations belong in consumer projects.

- **Forbidden:** Specific business entities like "orders", "courses", "tickets" (unless purely generic).
- **Allowed:** Domain-neutral placeholders like `knowledge-base`, `search`, `records`, `catalog`.

### Why This Matters

The framework is platform-agnostic. Vendor-specific code creates false coupling and misleads future contributors about the framework's scope.

## Rule 7: Consumer Agents Inherit from OrchidAgent

Consumer agents must subclass `OrchidAgent` and use inherited methods:

- `self.summarise()` — for LLM synthesis.
- `self.fetch_rag_context()` — for RAG retrieval.
- `self.extract_user_query()` — for query extraction.
- `self.extract_conversation_history()` — for history extraction.

These methods should never be duplicated in consumer agents.

## Rule 8: MCP Boundaries Use Broad Exception Handling

MCP server communication boundaries (`mcp_dispatcher.py`, `strategies.py`) catch `Exception` (not a narrow tuple) at server/tool call boundaries:

```python
try:
    result = await client.call_tool(name, args, auth)
except Exception:
    logger.warning("MCP tool call failed: %s", name)
    # Continue with remaining tools
```

### Why This Matters

MCP servers can fail with HTTP errors (401, 500), transport errors, or protocol errors. HTTP libraries like `httpx` raise exception types like `httpx.HTTPStatusError` that are not subclasses of `ConnectionError`/`TimeoutError`/`OSError`. A narrow exception tuple lets these propagate and crash the agent. One failing MCP server must not take down the entire agent.

## Rule 9: No API/CLI Code in the Library

The `orchid/` package contains only framework code. API endpoints belong in `orchid-api/`. CLI commands belong in `orchid-cli/`. The library has no FastAPI dependency, no Typer dependency, no CLI entry points.

### Why This Matters

The library should be usable as a pure Python dependency without pulling in web server or CLI dependencies. This keeps the library lightweight and flexible.

## Rule 10: OrchidAuthContext Is Treated as Immutable

While `OrchidAuthContext` is subclass-friendly (no `__slots__`, no `frozen=True`), framework code must treat it as immutable. Never modify an `OrchidAuthContext` after creation.

### Why This Matters

The auth context is shared across multiple graph nodes and agents. Mutating it can cause race conditions and inconsistent state.

## Rule 11: Handle _reader Being None

The vector backend can be `null` in tests or deployments without RAG. Always check if `self._reader` is `None` before calling retrieval methods:

```python
if self._reader is not None:
    docs = await self.fetch_rag_context(query, scope)
```

### Why This Matters

Agents should work without RAG. The `NullVectorReader` is used when no reader is configured, but explicit `None` checks are clearer and avoid unnecessary method calls.

## Rule 12: No HTTP/Fetch Logic in OrchidAuthConfigProvider

`OrchidAuthConfigProvider` is a pure config-resolution ABC. It reads environment variables seeded from `orchid.yml` but makes no network calls. Network calls to validate the discovery block happen one layer up in `orchid-api`'s router.

### Why This Matters

The provider should be testable without network access. Network validation is a separate concern that belongs in the API layer.
