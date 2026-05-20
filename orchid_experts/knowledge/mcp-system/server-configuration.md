<!-- Source: derived from orchid-website/src/content/concepts/mcp.mdx, orchid/README.md, and codebase analysis -->

# Server Configuration

MCP servers are configured per-agent in the `mcp_servers` section of `agents.yaml`. Each server entry defines how the agent connects to the MCP server, which tools to use, and how to handle authentication.

## Configuration Structure

```yaml
agents:
  my-agent:
    mcp_servers:
      - name: local-tools
        type: local
        transport: streamable_http
        url: http://localhost:3001/mcp
        tools: "*"
        auth:
          mode: none

      - name: external-crm
        type: remote
        transport: streamable_http
        url: ${CRM_MCP_URL}
        tools:
          - name: search
            arguments:
              max_results: 10
          - name: lookup
        auth:
          mode: oauth
```

## Fields

### name

Unique identifier for this MCP server within the agent. Used in logging, error messages, and as a key for tool source references (`source: "local-tools"`).

### type

- `"local"` — Co-deployed with the agent (same Docker network). Affects connection handling.
- `"remote"` — External service accessed over the network. Different retry behavior.

### transport

- `"streamable_http"` — Standard stateless protocol (recommended).
- `"sse"` — Server-Sent Events for streaming responses.

### url

The MCP server's HTTP endpoint. Supports `${VAR_NAME}` interpolation for environment variables.

### tools

Either:
- An explicit list of `ToolConfig` objects (allowlist):
  ```yaml
  tools:
    - name: search
      arguments:
        max_results: 10
    - name: lookup
  ```
- The wildcard `"*"` to auto-discover all tools at runtime.

### ToolConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | (required) | Tool name as reported by the server. |
| `arguments` | `dict` | `{}` | Default arguments for every invocation. |
| `inject_to_rag` | `bool` | `false` | Store results in vector store. |
| `rag_ttl` | `int\|null` | `null` | Cache TTL override. |

### prompts

Prompt template names or `"*"` to load all.

### resources

Resource URIs or `"*"` to load all.

### tool_call_strategy

Controls how multiple tools are executed:

- `"all"` — Call all matched tools simultaneously.
- `"sequential"` — Call tools one by one, passing results forward.
- `"llm_decides"` — Let the LLM decide which tools to call.

### auth

Authentication mode (see auth-modes.md):
- `mode: "none"` (default)
- `mode: "passthrough"`
- `mode: "oauth"`

## Environment Variable Interpolation

URLs can reference environment variables:

```yaml
url: ${CRM_MCP_URL}
```

Variables are resolved from the environment at config load time.

## Per-Agent Server Lists

Each agent can have its own MCP servers. This allows different agents to connect to different servers:

```yaml
agents:
  search-agent:
    mcp_servers:
      - name: search-api
        url: http://search:3001/mcp

  catalog-agent:
    mcp_servers:
      - name: catalog-api
        url: http://catalog:3001/mcp
```
