<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, and codebase analysis -->

# MCP Dispatcher

The `MCPDispatcher` is the collaborator responsible for discovering and calling MCP tools within an agent. It runs during step 3 of the GenericAgent pipeline and handles capability discovery, tool invocation, and error isolation.

## Role in the Pipeline

The `MCPDispatcher` runs during step 3 of the GenericAgent pipeline:

1. **Step 1: RAG Retrieval** — Retrieve relevant documents.
2. **Step 2: Skill Detection** — Check for matching skills.
3. **Step 3: MCP Tool Calls** — The `MCPDispatcher` discovers and calls MCP tools.
4. **Step 4: Built-in Tool Calls** — Call built-in Python tools.
5. **Step 5: Dynamic RAG Injection** — Retrieve cached tool results.
6. **Step 6: LLM Summarization** — Synthesize response.

## Core Functions

### render_capabilities()

Renders available MCP tools for the LLM to decide which to call:

```python
capabilities = await dispatcher.render_capabilities(
    mcp_servers=agent.mcp_servers,
    auth_context=auth,
)
```

This uses cached capabilities if warmed; otherwise, it performs discovery RPCs.

### call_mcp_tools()

Calls the selected MCP tools:

```python
results = await dispatcher.call_mcp_tools(
    tool_calls=llm_tool_calls,
    mcp_servers=agent.mcp_servers,
    auth_context=auth,
    strategy="all",
)
```

Results are returned as a dict mapping tool names to their results.

## Capability Discovery

When capabilities are not cached, the `MCPDispatcher`:

1. Calls `list_tools(auth)` on each MCP server.
2. Calls `list_prompts(auth)` on each MCP server.
3. Calls `list_resources(auth)` on each MCP server.
4. Caches results for the session lifetime.
5. Renders the discovered capabilities for the LLM.

## Tool Call Strategies

The `MCPDispatcher` executes tool calls according to the configured strategy:

- **`all`** — Call every matched tool simultaneously.
- **`sequential`** — Call tools one by one, passing accumulated results forward.
- **`llm_decides`** — Let the LLM decide which tools to call.

The strategy is configured per MCP server in `agents.yaml`.

## Error Isolation

The `MCPDispatcher` uses broad exception handling at MCP communication boundaries:

```python
try:
    result = await mcp_client.call_tool(name, args, auth)
except Exception:
    logger.warning("MCP tool call failed: %s", name)
    # Continue with remaining tools
```

### Why Broad Exception Handling?

MCP servers can fail with various errors:

- HTTP errors (401 Unauthorized, 500 Internal Server Error).
- Connection failures (timeout, DNS, refused).
- Protocol errors (invalid JSON, unexpected responses).
- Transport errors (stdio pipe broken, SSE stream closed).

HTTP libraries like `httpx` raise exception types like `httpx.HTTPStatusError` that are not subclasses of `ConnectionError`/`TimeoutError`/`OSError`. A narrow exception tuple would let these propagate and crash the agent.

### Fault Isolation Guarantee

One failing MCP server never takes down the entire agent. The agent continues with:

- Results from successful tools.
- Error messages for failed tools (included in the LLM context).
- Remaining MCP servers unaffected.

This applies to:
- Tool execution (strategies).
- Capability discovery (`render_capabilities`).
- The `fetch()` dispatcher.

## Configuration

The `MCPDispatcher` has no independent configuration. It uses:

- The agent's `mcp_servers` configuration.
- The `OrchidMCPClient` instances created from server configs.
- The MCP auth context from the graph state.

## Integration with GenericAgent

The `GenericAgent` delegates to the `MCPDispatcher` during step 3:

```python
# In GenericAgent.run()
if self.mcp_servers and self.mcp_dispatcher:
    capabilities = await self.mcp_dispatcher.render_capabilities(
        self.mcp_servers, auth_context
    )
    tool_calls = await self._decide_mcp_tools(query, capabilities)
    mcp_results = await self.mcp_dispatcher.call_mcp_tools(
        tool_calls, self.mcp_servers, auth_context, strategy
    )
```
