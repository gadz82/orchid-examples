<!-- Source: derived from orchid-website/src/content/concepts/mcp.mdx, orchid/AGENTS.md, orchid-mcp/AGENTS.md, and codebase analysis -->

# MCP Basics

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to LLMs. In Orchid, MCP servers provide external tools that agents can call, extending their capabilities beyond built-in Python tools.

## MCP in Orchid

Orchid's MCP integration has three components:

### 1. MCP Client (Framework Library)

The `StreamableHttpMCPClient` in `orchid_ai/mcp/client.py` implements the MCP client protocol:

- Discovers tools, prompts, and resources from MCP servers.
- Calls MCP tools with arguments and receives results.
- Manages three auth modes: `none`, `passthrough`, `oauth`.
- Caches capabilities for the process/session lifetime.

### 2. MCP Gateway (TypeScript)

The `orchid-mcp` TypeScript package is an MCP server that exposes Orchid to any MCP-capable host LLM (e.g., Claude Desktop, Cursor):

- Provides 6 MCP tools: `orchid_ask`, `orchid_new_chat`, `orchid_list_chats`, `orchid_upload_file`, `orchid_resume_chat`.
- Connects to `orchid-api` over HTTP.
- Manages MCP sessions with LRU caching.
- Implements OAuth service-account and authorization-server roles.

### 3. MCP Gateway Exposure Config

The `mcp_gateway` block in `agents.yaml` customizes how the MCP gateway presents itself:

```yaml
mcp_gateway:
  tools:
    orchid_ask:
      title: "Ask the Acme Knowledge Base"
      description: "Route a question to the support agents."
```

## Discovery and Capability Caching

When an agent connects to an MCP server, it discovers the server's capabilities (tools, prompts, resources). This discovery is cached to avoid repeated RPCs:

### Discovery Methods

- `list_tools(auth)` — Discover available tools.
- `list_prompts(auth)` — Discover available prompts.
- `list_resources(auth)` — Discover available resources.

### Cache Lifecycle

Capabilities are cached for the process/session lifetime:

- **`auth.mode: none` servers** — Warmed at process startup.
- **`auth.mode: passthrough` or `oauth` servers** — Warmed once per `(tenant_key, user_id)` at session start.

The cache is warmed proactively by `OrchidSessionWarmer` — the per-request hot path stops paying the discovery cost once the cache is populated.

## Tool Allowlisting

Each MCP server can be configured to expose only specific tools:

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools:
      - name: search_catalog
      - name: get_inventory
    # Only these two tools are exposed
```

Or use the wildcard `"*"` to expose all tools:

```yaml
mcp_servers:
  - name: my-server
    url: http://localhost:3001/mcp
    tools: "*"
    # All tools are exposed
```

## Fault Isolation

MCP server communication boundaries use broad exception handling. If a server returns HTTP errors (401, 500), connection failures, or protocol errors, the agent logs a warning and continues with remaining servers and tools. One failing MCP server never takes down the entire agent.

## Transport Types

| Transport | Description |
|-----------|-------------|
| `streamable_http` | Standard stateless HTTP protocol (recommended). |
| `sse` | Server-Sent Events for streaming responses. |
| `stdio` | Standard input/output (for local MCP servers). |

Streamable HTTP is the recommended transport for most deployments.
