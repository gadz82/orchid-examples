<!-- Source: derived from orchid-website/src/content/concepts/tool-strategies.mdx, orchid/AGENTS.md, and codebase analysis -->

# Tool Strategies

Tool strategies control how multiple tools are executed when an agent has more than one tool to call. Orchid provides three built-in strategies and supports custom strategy implementations.

## Strategy Registry

Tool call strategies are registered in a global registry:

```python
from orchid_ai.agents.strategies import register_strategy

class MyStrategy(OrchidToolCallStrategy):
    async def execute(self, tools, query, context):
        # Custom strategy logic
        ...

register_strategy("my_strategy", MyStrategy())
```

## Built-in Strategies

### all Strategy

Call every matched tool simultaneously and collect all results.

#### How It Works

1. The LLM decides which tools to call.
2. All selected tools are called in parallel.
3. Results are collected independently.
4. All results are included in the LLM context.

#### Configuration

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
    tool_call_strategy: all
```

#### When to Use

- Tools are independent (don't depend on each other's output).
- You want the fastest execution (parallel calls).
- You need results from all matched tools.

#### Trade-offs

- Fastest strategy (parallel execution).
- Tools run independently — they can't see each other's output.
- May waste resources calling tools that aren't needed.

### sequential Strategy

Call tools one by one in order. Each tool receives the accumulated results from previous tools.

#### How It Works

1. The LLM decides which tools to call.
2. Tools are called in order (as listed in the configuration).
3. Each tool receives a `previous_results` argument with accumulated results.
4. Results are accumulated and passed to the next tool.

#### Configuration

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
    tool_call_strategy: sequential
```

#### When to Use

- Tools depend on each other's output (e.g., search → filter → sort).
- You need to pass context from one tool to the next.
- Order matters.

#### Trade-offs

- Slower than `all` (sequential execution).
- Each tool sees accumulated results from previous tools.
- More powerful but more expensive.

### llm_decides Strategy

Ask the LLM to decide which tools to call and with what arguments.

#### How It Works

1. The LLM sees all available tools and the user query.
2. The LLM generates tool calls (which tools, with what arguments).
3. Tools are called based on the LLM's decisions.
4. Results are collected and included in the context.

#### Configuration

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
    tool_call_strategy: llm_decides
```

#### When to Use

- You want maximum flexibility in tool selection.
- The LLM can make better decisions than a fixed strategy.
- You have many tools and don't want to call all of them.

#### Trade-offs

- Most flexible but slowest (extra LLM call).
- Uses more tokens (tool descriptions in the prompt).
- The LLM may make suboptimal decisions.

## Custom Strategies

To implement a custom strategy:

1. Subclass `OrchidToolCallStrategy`.
2. Implement the `execute()` method.
3. Register it with the strategy registry.

```python
from orchid_ai.agents.strategies import OrchidToolCallStrategy, register_strategy

class ConditionalStrategy(OrchidToolCallStrategy):
    async def execute(self, tools, query, context, **kwargs):
        # Analyze the query to decide which tools to call
        if "weather" in query.lower():
            # Call weather tools
            ...
        elif "data" in query.lower():
            # Call data tools
            ...
        return results

register_strategy("conditional", ConditionalStrategy())
```

Then use it in YAML:

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
    tool_call_strategy: conditional
```

## Strategy Selection Guide

| Strategy | Speed | Flexibility | Tool Dependencies |
|----------|-------|-------------|-------------------|
| `all` | Fastest | Low | Independent tools |
| `sequential` | Medium | Medium | Dependent tools |
| `llm_decides` | Slowest | High | Any |
| Custom | Depends | Depends | Depends |

## Per-Server Configuration

Each MCP server can have its own tool call strategy:

```yaml
mcp_servers:
  - name: independent-tools
    url: http://localhost:3001/mcp
    tools: "*"
    tool_call_strategy: all

  - name: dependent-tools
    url: http://localhost:3002/mcp
    tools: "*"
    tool_call_strategy: sequential
```

This allows you to use the right strategy for each server's tool set.

## Built-in Tool Strategy

Built-in tools always use the `all` strategy (parallel execution). There is no per-tool strategy configuration for built-in tools — they are always called in parallel based on the LLM's decisions.

## Strategy and Parallel Safety

The `execution_hints.parallel_safe` hint on agents interacts with tool strategies:

- **`parallel_safe: true`** — The supervisor may run this agent concurrently with other agents. Within the agent, tools are called according to the configured strategy.
- **`parallel_safe: false`** — The supervisor runs this agent sequentially. Within the agent, tools are called according to the configured strategy.

The agent-level parallel safety hint doesn't affect the tool-level strategy — it only affects how the supervisor schedules the agent relative to other agents.
