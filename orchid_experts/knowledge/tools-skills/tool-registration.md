<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/agents.mdx, and codebase analysis -->

# Tool Registration

Tool registration is the process of making Python functions available as built-in tools that agents can call. Orchid supports two registration methods: YAML declaration and programmatic registration.

## YAML Registration

Tools are declared in the `tools` section of `agents.yaml`:

```yaml
tools:
  get_weather:
    handler: myapp.tools.weather.get_weather
    description: "Get current weather for a city"
  search_catalog:
    handler: myapp.tools.catalog.search
    description: "Search the product catalog"
```

### How It Works

1. At graph build time, `load_config()` reads the `tools` section.
2. Each tool's `handler` is imported via `importlib` from the dotted path.
3. The tool is registered in the global tool registry.
4. Agents reference tools by name in their `tools` list.

### Handler Requirements

The handler function must:

- Be importable from the working directory.
- Be callable with keyword arguments `query` and `context`.
- Return a string (the tool result).

```python
def get_weather(query: str, context: dict) -> str:
    """Get current weather for a city."""
    return f"Weather in {query}: Sunny, 25°C"
```

## Programmatic Registration

Tools can also be registered programmatically:

```python
from orchid_ai.config.tool_registry import register_tool

def get_weather(query: str, context: dict) -> str:
    return f"Weather in {query}: Sunny, 25°C"

register_tool("get_weather", get_weather, description="Get current weather for a city")
```

### When to Use Programmatic Registration

- **Dynamic tools** — Tools that are generated or discovered at runtime.
- **Test tools** — Tools registered during test setup.
- **Plugin tools** — Tools registered by plugins at startup.

## Parameter Auto-Extraction

When parameters are not declared in YAML, they are auto-extracted from the Python function signature via `inspect`:

```python
def get_weather(city: str, units: str = "celsius") -> str:
    ...
```

Auto-extracted parameters:

| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `city` | `str` | Yes | None |
| `units` | `str` | No | `"celsius"` |

### Framework Parameter Filtering

Framework-injected params are filtered out automatically:

- `query` — The user's query.
- `context` — Accumulated context.
- `auth_context` — The auth context.
- `**kwargs` — Additional keyword arguments.

These are not exposed to the LLM as tool parameters.

### YAML Parameter Override

YAML parameter declarations take precedence over auto-extracted parameters:

```yaml
tools:
  get_weather:
    handler: myapp.tools.weather.get_weather
    parameters:
      city:
        type: string
        description: "The city name (e.g., San Francisco)"
        required: true
```

This overrides the auto-extracted `city` parameter with a custom description.

## Tool Registry

The tool registry is a global dictionary that maps tool names to tool metadata:

```python
from orchid_ai.config.tool_registry import TOOL_REGISTRY

# Access a registered tool
tool = TOOL_REGISTRY.get("get_weather")
```

### Tool Metadata

Each registered tool has:

- **`name`** — Tool name (key in the registry).
- **`handler`** — The Python function.
- **`description`** — Human-readable description.
- **`parameters`** — Parameter metadata (from YAML or auto-extracted).
- **`inject_to_rag`** — Whether to cache results in RAG.
- **`rag_ttl`** — Cache TTL.

## CLI Skill Generation

Parameter metadata is used by the CLI skill generator (`orchid skill generate`) to produce accurate Claude Code skill documentation:

```bash
orchid skill generate --config agents.yaml
```

The generator reads tool parameters from the registry and generates skill docs with accurate parameter descriptions, types, and defaults.

## Best Practices

- **Use YAML registration for static tools** — It's the most common and maintainable approach.
- **Use programmatic registration for dynamic tools** — When tools are generated at runtime.
- **Write clear descriptions** — The LLM uses descriptions to decide when to call tools.
- **Declare parameters in YAML** — When you need custom descriptions or defaults.
- **Keep handlers simple** — Tools should do one thing well and return a string result.
- **Test handlers independently** — Tool handlers should be testable without the full agent pipeline.
