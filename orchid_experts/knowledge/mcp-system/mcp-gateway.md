<!-- Source: derived from orchid-mcp/AGENTS.md, orchid-mcp/README.md, and codebase analysis -->

# MCP Gateway

The `orchid-mcp` TypeScript package is an MCP gateway that exposes Orchid to any MCP-capable host LLM (e.g., Claude Desktop, Cursor). It connects to `orchid-api` over HTTP and presents 6 MCP tools to host applications.

## Architecture

```
Claude Desktop / Cursor (MCP Host)
        │
        │ MCP Protocol (stdio / streamable-http)
        ▼
    orchid-mcp (Gateway)
        │
        │ HTTP (REST + SSE)
        ▼
    orchid-api (FastAPI)
        │
        │ LangGraph
        ▼
    Agents + RAG + MCP Servers
```

The gateway sits between MCP hosts and the Orchid API, translating MCP tool calls into Orchid API requests.

## MCP Tools

The gateway exposes 6 MCP tools:

| Tool | Description |
|------|-------------|
| `orchid_ask` | Send a message and get a response. |
| `orchid_new_chat` | Create a new chat session. |
| `orchid_list_chats` | List existing chat sessions. |
| `orchid_upload_file` | Upload a file to a chat. |
| `orchid_resume_chat` | Resume an existing chat by ID. |

## Auth Strategies

The gateway supports multiple auth strategies:

### Service Account

For automated MCP hosts that authenticate with a service account:

```json
{
  "orchidApiKey": "sk-...",
  "tenantId": "my-tenant"
}
```

### OAuth AS (Authorization Server) Role

The gateway can act as an OAuth authorization server, enabling dynamic client registration (DCR) for MCP hosts. This follows the MCP 2025-03-26 authorization spec.

### Token Proxy Pattern

For NextAuth v5 integrations, the gateway proxies OAuth tokens from the frontend to the API, avoiding CORS and token exposure to the browser.

## Session Management

The gateway manages MCP sessions using an LRU cache:

- Sessions map MCP sessions to Orchid chat sessions.
- LRU eviction prevents unbounded memory growth.
- Configurable max sessions and TTL.

## Observability

The gateway includes:

- **Pino logger** — Structured JSON logging.
- **AsyncLocalStorage** — Correlation ID tracking across async boundaries.
- **OpenTelemetry** — Distributed tracing.
- **Rate limiting** — Token-bucket rate limiter per MCP session.

## Configuration

The `mcp_gateway` block in `agents.yaml` customizes how the gateway presents itself:

```yaml
mcp_gateway:
  tools:
    orchid_ask:
      title: "Ask the Acme Knowledge Base"
      description: "Route a question to the support agents."
```

Tool overrides change the `title` and `description` that MCP hosts see when they discover tools. Default titles/descriptions are in `orchid-mcp/src/tools/`.

## Prompts

The gateway can also expose MCP prompts:

```yaml
mcp_gateway:
  prompts:
    - name: compliance_report
      description: "Generate a compliance report."
      arguments:
        - { name: department, required: true }
      template: |
        Produce a compliance report for {{department}}.
```

Prompts are pre-canned templates with `{{var}}` substitution.

## Deployment

The gateway is a standalone Node.js process:

```bash
cd orchid-mcp
npm install
npm run build
npm start
```

Configuration is via environment variables:

```bash
ORCHID_API_URL=http://orchid-api:8000
ORCHID_MCP_PORT=3100
ORCHID_MCP_AUTH_MODE=oauth
```

## Common Use Cases

1. **Claude Desktop integration** — Add orchid-mcp to claude_desktop_config.json.
2. **Cursor** — Add orchid-mcp to Cursor's MCP server list.
3. **Custom MCP hosts** — Any application implementing the MCP client protocol.
4. **CLI tools** — Use orchid-mcp as a bridge between CLI tools and Orchid.
