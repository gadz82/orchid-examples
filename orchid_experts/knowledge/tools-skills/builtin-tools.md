<!-- Source: derived from orchid-website/src/content/concepts/tool-strategies.mdx, orchid-website/src/content/concepts/agents.mdx, and codebase analysis -->

# Built-in Tools

Built-in tools are Python functions registered as in-process tool handlers that agents can call during their pipeline. Unlike MCP tools (which call external servers), built-in tools run within the same Python process, with no network overhead.

## The @tool Decorator

The `@tool` decorator registers a Python function as a built-in tool:

```python
from orchid_ai.agents.tools import tool

@tool
def get_weather(query: str, context: dict) -> str:
    """Get current weather for a city."""
    # Tool logic here
    return f"Weather in {query}: Sunny, 25°C"
```

The decorator:

1. Extracts the function's signature to determine parameters.
2. Uses the docstring as the tool description.
3. Registers the tool in the global tool registry.

### Parameters

The tool function receives:

- **`query`** — The user's query or the specific question for this tool call.
- **`context`** — Accumulated context from previous tool calls and RAG retrieval.
- **`**kwargs`** — Additional parameters passed by the framework.

Framework-injected params (`query`, `context`, `auth_context`, `**kwargs`) are filtered out automatically when generating the tool schema for the LLM.

## Declarative Parameter Metadata

Tool parameters can be declared in YAML instead of auto-extracted from the function signature:

```yaml
tools:
  get_weather:
    handler: myapp.tools.get_weather
    description: "Get current weather for a city"
    parameters:
      city:
        type: string
        description: "The city name"
        required: true
      units:
        type: string
        description: "Temperature units (celsius or fahrenheit)"
        required: false
        default: "celsius"
```

### When to Use YAML Parameters

- **Override auto-extraction** — When the function signature includes framework params that shouldn't be exposed to the LLM.
- **Add descriptions** — When the function signature doesn't have enough context for the LLM.
- **Set defaults** — When you want to provide default values for optional parameters.
- **Control types** — When you want to enforce specific types that differ from Python type hints.

### Priority

YAML parameter declarations take precedence over auto-extracted parameters. When both are present, YAML wins.

## Tool Registration

Tools are registered in the global tool registry:

```python
from orchid_ai.config.tool_registry import register_tool

def my_tool(query: str, context: dict) -> str:
    return "Result"

register_tool("my_tool", my_tool, description="My tool description")
```

Or via YAML in `agents.yaml`:

```yaml
tools:
  my_tool:
    handler: myapp.tools.my_tool
    description: "My tool description"
```

## Tool Configuration in agents.yaml

```yaml
tools:
  get_weather:
    handler: myapp.tools.weather.get_weather
    description: "Get current weather temperature and conditions for a city name"
    inject_to_rag: false
    rag_ttl: null
```

### Fields

- **`handler`** — Dotted Python import path to the tool function (required). Imported via `importlib` at graph build time.
- **`description`** — Human-readable description for the LLM. Be specific about what the tool does.
- **`parameters`** — Optional parameter declarations (see above).
- **`inject_to_rag`** — Store tool results in vector store for future retrieval. Default: `false`.
- **`rag_ttl`** — Per-tool RAG cache TTL in seconds. Default: `null` (uses agent's `rag.rag_ttl`).

## Tool Invocation

When an agent has built-in tools configured:

1. The LLM decides which tools to call based on the query and tool descriptions.
2. The tool is called in-process (no network overhead).
3. The result is included in the LLM context for summarization.
4. If `inject_to_rag: true`, the result is stored in the vector store.

## Tool Return Values

Tools should return strings. The return value is included in the LLM context as:

```
Tool result for get_weather:
Weather in San Francisco: Foggy, 15°C
```

If a tool returns a complex object, convert it to a string representation:

```python
import json

def get_catalog(query: str, context: dict) -> str:
    catalog = {"products": [...], "total": 100}
    return json.dumps(catalog, indent=2)
```

## Error Handling

Tools should handle their own errors and return error messages as strings:

```python
@tool
def get_weather(query: str, context: dict) -> str:
    try:
        # Tool logic
        return f"Weather in {query}: Sunny, 25°C"
    except Exception as e:
        return f"Error getting weather: {str(e)}"
```

The framework does not catch tool errors — the tool is responsible for returning a meaningful error message.

## Best Practices

- **Be specific in descriptions** — "Get current weather temperature and conditions for a city name" is better than "Weather tool".
- **Handle errors gracefully** — Return error messages as strings, don't raise exceptions.
- **Use inject_to_rag for expensive calls** — Cache results of expensive API calls.
- **Keep tools focused** — Each tool should do one thing well.
- **Test tools independently** — Tools should be testable without the full agent pipeline.
