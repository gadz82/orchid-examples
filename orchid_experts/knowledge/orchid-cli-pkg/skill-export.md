<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# Skill Export

The CLI can generate Claude Code skill documentation from built-in tools declared in `agents.yaml`. These skills enable Claude Code (and other LLM hosts) to understand and use Orchid's tools with accurate parameter metadata.

## Skill Generation Command

```bash
orchid skill generate \
  --config agents.yaml \
  --output skills/
```

Generates one markdown skill file per built-in tool in the `tools` section of `agents.yaml`.

## What It Generates

For each tool, the generator produces a self-contained markdown skill file with:

### Tool Identity
- **Name** — The tool key from `agents.yaml`.
- **Description** — From the tool's `description` field.
- **Handler path** — The dotted Python import path (`handler: myapp.tools.weather.get_weather`).

### Parameters
Each parameter is documented with:
- **Name** — Parameter name.
- **Type** — `string`, `int`, `float`, or `bool`.
- **Description** — From YAML `parameters.*.description` or inferred from docstring.
- **Required** — Whether the parameter is mandatory.
- **Default** — If the parameter has a default value.

### Usage Examples
Generated from parameter metadata, showing both required and optional parameters.

### Example Output

```markdown
# get_weather

Get current weather temperature and conditions for a city name. This tool
uses the OpenWeatherMap API to fetch real-time weather data.

## Parameters

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `city` | string | Yes | — | The city name (e.g., "San Francisco") |
| `units` | string | No | `"celsius"` | Temperature units: celsius or fahrenheit |

## Usage

Getting weather for San Francisco in Celsius:
```
weather = get_weather(city="San Francisco")
// → "San Francisco: 18°C, Partly Cloudy"
```

Getting weather in Fahrenheit:
```
weather = get_weather(city="New York", units="fahrenheit")
// → "New York: 72°F, Sunny"
```

## Handler

```
myapp.tools.weather.get_weather
```
```

## Parameter Metadata Source

Parameters come from two sources, with YAML declarations taking precedence:

### 1. YAML Declarations (Preferred)

```yaml
tools:
  get_weather:
    handler: myapp.tools.weather.get_weather
    description: "Get current weather for a city"
    parameters:
      city:
        type: string
        description: "The city name (e.g., San Francisco)"
        required: true
      units:
        type: string
        description: "Temperature units"
        required: false
        default: "celsius"
```

YAML declarations give you full control over parameter descriptions and types.

### 2. Auto-Extracted from Function Signature (Fallback)

When parameters are omitted, the generator inspects the Python function:

```python
def get_weather(city: str, units: str = "celsius") -> str:
    """Get current weather for a city."""
    ...
```

Auto-extracted parameters: `city (str, required)`, `units (str, default=celsius)`.

Framework-injected params (`query`, `context`, `auth_context`, `**kwargs`) are automatically filtered out from the skill documentation.

## Output Directory

Generated files are placed in the output directory, one per tool:

```
skills/
├── get_weather.md
├── search_catalog.md
├── get_inventory.md
├── create_order.md
└── ...
```

## Refreshing Skills

Re-run the generator whenever tools change:

```bash
orchid skill generate --config agents.yaml --output skills/ --force
```

The `--force` flag overwrites existing skill files. Without it, existing files are skipped.

## CLI Skill Integration with Claude Code

After generation, Claude Code can read these skill files to understand available tools and their parameters. This enables:
- Accurate tool invocation with correct parameter types.
- Automatic parameter validation based on declared types.
- Context-aware tool recommendations based on descriptions.

## Best Practices

- **Write detailed tool descriptions** in YAML — the LLM uses these to decide when to call tools.
- **Declare parameters in YAML** for tools with non-obvious parameter names or types.
- **Use descriptive parameter descriptions** — they help the LLM provide correct arguments.
- **Regenerate skills after tool changes** — stale skill docs lead to incorrect tool usage.
- **Review generated skills** for accuracy before deploying to production.
