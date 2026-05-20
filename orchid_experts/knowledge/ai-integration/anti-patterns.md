<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid/AGENTS.md, and codebase analysis -->

# Anti-Patterns

Common mistakes and anti-patterns to avoid when building with Orchid.

## Parse-Once Violations

**Problem:** Parsing the same document twice — once for the prompt, once for RAG ingestion.

```python
# WRONG
prompt = await extract_text(file_bytes, filename)  # Parse #1
await ingest_document(file_bytes=file_bytes, ...)   # Parse #2 (in ingest_document)
```

**Fix:** Use the parse-once pattern:

```python
# CORRECT
content = await extract_text(file_bytes, filename)  # Parse once
prompt = f"Document:\n{content}\n\nQuestion: {query}"
await ingest_document(file_bytes=file_bytes, pre_extracted_text=content, ...)
```

## Raw tenant_id Filters

**Problem:** Passing raw `tenant_id` filters instead of using `OrchidRAGScope`.

```python
# WRONG
docs = await reader.retrieve(query, filters={"tenant_id": "my-tenant"}, k=5)
```

**Fix:** Always use `OrchidRAGScope`:

```python
# CORRECT
scope = OrchidRAGScope(tenant_id="my-tenant", user_id="seed", chat_id="", agent_id="")
docs = await reader.retrieve(query, scope=scope, k=5)
```

## Importing Concrete Backends in Agent Code

**Problem:** Importing `qdrant_client` or other concrete implementations in agent code.

```python
# WRONG (in agent code)
from qdrant_client import QdrantClient
```

**Fix:** Use the abstract interfaces:

```python
# CORRECT
docs = await self.reader.retrieve(query, scope=scope, k=5)
```

## Persisting Augmented Prompts

**Problem:** Saving the augmented prompt (with file content) to chat history instead of the original user message.

```python
# WRONG
augmented_message = f"Document content:\n{doc_text}\n\nUser question: {user_query}"
await storage.add_message(chat_id, "user", augmented_message)
```

**Fix:** Save the original message:

```python
# CORRECT
await storage.add_message(chat_id, "user", user_query)
```

## Not Handling Null Reader

**Problem:** Assuming the vector reader is always available.

```python
# WRONG
docs = await self._reader.retrieve(...)  # AttributeError if _reader is None
```

**Fix:** Check for None:

```python
# CORRECT
if self._reader is not None:
    docs = await self._reader.retrieve(...)
```

## Catching Narrow Exceptions at MCP Boundaries

**Problem:** Catching only `ConnectionError` at MCP call boundaries.

```python
# WRONG
try:
    result = await client.call_tool(name, args)
except (ConnectionError, TimeoutError):
    logger.warning("MCP call failed")
```

**Fix:** Use broad `Exception` catching at MCP boundaries:

```python
# CORRECT
try:
    result = await client.call_tool(name, args)
except Exception:
    logger.warning("MCP call failed: %s", name)
```

## Mutating OrchidAuthContext

**Problem:** Modifying `OrchidAuthContext` after creation.

```python
# WRONG
auth_context.tenant_key = "new-tenant"
```

**Fix:** Create a new context if you need different values:

```python
# CORRECT
new_auth = OrchidAuthContext(
    access_token=auth_context.access_token,
    tenant_key="new-tenant",
    user_id=auth_context.user_id,
)
```

## Importing litellm at Module Level

**Problem:** Consumer agents importing `litellm` at module level for simple summarization.

```python
# WRONG (module-level import)
import litellm

class MyAgent(OrchidAgent):
    async def run(self, state):
        response = await litellm.acompletion(...)
```

**Fix:** Use `self.summarise()` for simple completions, and only lazy-import `litellm` inside methods when you need tool-calling responses.
