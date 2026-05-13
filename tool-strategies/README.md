# Tool-strategies showcase

Demonstrates Orchid's two orthogonal tool-dispatch extension points:

1. **`tool_call_strategy`** — per-MCP-server choice of how a skill's
   tool list is invoked. Built-ins: `all`, `sequential`,
   `llm_decides`. Plus a custom `priority` strategy registered by
   this example's startup hook.
2. **`parallel_tools`** — per-agent flag enabling the agentic-loop's
   Phase A parallel dispatch within a single round. Independent of
   `tool_call_strategy`; applies to native `tool_calls` only.

## Files

```
examples/tool-strategies/
├── README.md
├── __init__.py
├── orchid.yml                    # startup.hook + storage + LLM
├── agents.yaml                   # 5 agents, each highlighting one knob
├── hooks/
│   ├── __init__.py
│   └── startup.py                # registers the `priority` strategy
├── strategies/
│   ├── __init__.py
│   └── priority.py               # OrchidToolCallStrategy subclass
└── tools/
    ├── __init__.py
    └── metrics.py                # parallel-safe built-in tools
```

## What each agent demonstrates

| Agent | Knob | Strategy / flag | When to use |
|---|---|---|---|
| `fanout_lookup` | `tool_call_strategy` | `all` | Independent backends, lowest-latency wins |
| `pipeline_lookup` | `tool_call_strategy` | `sequential` | Tool N depends on tool N-1's output |
| `smart_lookup` | `tool_call_strategy` | `llm_decides` | LLM picks the relevant subset |
| `cascade_lookup` | `tool_call_strategy` | `priority` (custom) | Cache → DB → upstream short-circuit |
| `parallel_searcher` | `parallel_tools` | flag (Phase A) | Agentic-loop intra-round parallelism |

## Where strategies actually run

Critical detail (often missed): `tool_call_strategy` is consulted by
**skill-execution paths only**. The default agentic loop — where the
LLM chooses tools via native `tool_calls` — does NOT honour it. That
loop always behaves as "LLM decides".

This example surfaces the strategies through explicit per-agent
`skills:` blocks so the dispatch path runs through `MCPDispatcher.fetch`,
which is where `get_strategy(server.tool_call_strategy)` is consulted.

## The custom `priority` strategy

`strategies/priority.py` subclasses `OrchidToolCallStrategy` and
implements a "first non-empty response wins" lookup chain:

```python
async def execute(self, client, tools, query, auth, *, agent_name="", **kwargs):
    for tool in tools:
        result = await client.call_tool(tool.name, args, auth)
        results[tool.name] = result.text
        if self._has_payload(result.text):
            break  # short-circuit
    return results
```

Registration happens in `hooks/startup.py`, wired to orchid.yml's
`startup.hook` field. The hook fires once at process startup so the
strategy is in `STRATEGY_REGISTRY` before any agent invokes it.

```python
# hooks/startup.py
async def bootstrap_strategies(reader, settings, **_):
    from orchid_ai.agents.strategies import register_strategy
    priority_module = importlib.import_module("examples.tool-strategies.strategies.priority")
    register_strategy("priority", priority_module.PriorityStrategy)
```

The example folder uses a hyphenated name (matching the rest of
`examples/`); Python's `import` statement can't parse hyphens, so the
hook goes through `importlib.import_module`, which accepts arbitrary
dotted strings.

## Parallel tool dispatch (`parallel_tools`)

The `parallel_searcher` agent opts in by setting `parallel_tools: true`
on its config. The agentic loop then partitions the LLM's `tool_calls`
into:

- **Parallel batch** — gathered via `asyncio.gather`. Includes built-in
  tools whose `parallel_safe` is True (set on `tools.<name>` at the
  top level of `agents.yaml`) and MCP tools with either explicit
  `parallel_safe: true` or an `readOnlyHint=true` server annotation.
- **Sequential tail** — everything else (tools requiring approval,
  unknown safety, write-side effects).

The metrics tools in this example are pure read-only stubs declared
`parallel_safe: true`, so a single agentic round running all three
takes ~50ms total instead of ~150ms.

## Running

```bash
# Validate the YAML loads (no MCP server needed for validation)
orchid config validate examples/tool-strategies/agents.yaml

# To exercise tool_call_strategy you need an MCP server reachable at
# $KB_MCP_URL exposing cache_lookup / primary_lookup / slow_lookup.
# The mcp-servers/ directory in this repo contains starter mocks.
KB_MCP_URL=http://localhost:9001/mcp \
  ORCHID_CONFIG=examples/tool-strategies/orchid.yml \
  uvicorn orchid_api.main:app --port 8000

# Try each agent:
#   curl -X POST http://localhost:8000/messages \
#     -d '{"agent": "cascade_lookup", "skill": "cascade", "query": "lookup foo"}'
```

## Adapting

To register your own strategy:

1. Subclass `OrchidToolCallStrategy` in your own module.
2. Implement `async def execute(self, client, tools, query, auth, *, agent_name="", **kwargs)`.
3. Call `register_strategy("my_strategy", MyStrategy)` from a startup
   hook (or from your application's composition root if you don't
   use orchid-api).
4. Reference it from YAML: `mcp_servers[*].tool_call_strategy: my_strategy`.

Strategy registration is process-wide, so register once at startup
and the same instance answers every agent's requests.
