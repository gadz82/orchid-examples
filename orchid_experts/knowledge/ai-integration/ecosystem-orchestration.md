<!-- Source: derived from orchid-website/src/content/packages/orchid.mdx, orchid-website/src/content/packages/orchid-api.mdx, orchid-website/src/content/best-practices.mdx, and codebase analysis -->

# Ecosystem Orchestration

How to wire all five Orchid packages together into a cohesive production system. Each package is a separate repository with independent stability guarantees, but they work together through well-defined interfaces.

## The Five Packages

```
orchid (Python library)      — Core ABCs, GenericAgent, graph builder
    ↑
    ├── orchid-api (FastAPI)  — HTTP server consumed by frontend + MCP gateway
    ├── orchid-cli (Typer)    — CLI tool, standalone, shares orchid.yml
    └── orchid-mcp (Node.js)  — MCP gateway that exposes Orchid to MCP hosts

orchid-frontend (Next.js) — Multi-chat UI, talks to orchid-api over HTTP
```

### Dependency Direction

The dependency graph is strictly one-way:
- `orchid-api/ → orchid/` (only)
- `orchid-cli/ → orchid/` (only)
- `orchid-frontend/ → orchid-api/` (HTTP only)
- `orchid-mcp/ → orchid-api/` (HTTP only)

No cross-package circular dependencies. Changes in `orchid/` must not break `orchid-api/` or `orchid-cli/`.

## Integration Patterns

### Pattern 1: Full Stack (API + Frontend)

```
User Browser → Next.js Frontend → orchid-api → Agents + RAG + Tools
                    ↑ HTTPS            ↑ Internal network
                (SSE streaming)   (REST + SSE endpoints)
```

The frontend proxies API calls through server actions. The browser never has direct access to the API. NextAuth manages OAuth sessions; the token proxy pattern keeps bearer tokens out of client-side JavaScript.

### Pattern 2: CLI Only

```
Developer Terminal → orchid-cli → Agents + RAG (in-process)
```

The CLI builds the graph in-process using the same `orchid.yml` configuration. No server needed. ChromaDB is the default vector backend for zero-infra local usage.

### Pattern 3: MCP Gateway

```
Claude Desktop / Cursor → orchid-mcp → orchid-api → Agents + RAG
   (MCP stdio/http)        (TypeScript)    (HTTP)
```

The MCP gateway translates MCP protocol tool calls into Orchid API requests. It manages MCP sessions, OAuth tokens, and rate limiting.

### Pattern 4: Embedded API

```python
from fastapi import FastAPI
from orchid_api.main import setup_orchid

app = FastAPI()
await setup_orchid(app)
```

Mount Orchid as a sub-application within an existing FastAPI project. Perfect for adding AI capabilities to an existing backend.

## Configuration Consistency

All packages share the same configuration files:

```yaml
# orchid.yml — consumed by API, CLI, and indirectly by frontend + MCP gateway
agents:
  config_path: examples/my-project/agents.yaml

llm:
  model: openai/gpt-4o
  ollama_api_base: http://localhost:11434

rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text

storage:
  class: orchid_ai.persistence.postgres.OrchidPostgresChatStorage
  dsn: postgresql+asyncpg://...

auth:
  identity_resolver_class: myproject.identity.MyResolver

startup:
  hook: myproject.hooks.seed_knowledge
```

The API and CLI read this file directly. The frontend reads a subset via the API's `/auth/info` endpoint. The MCP gateway reads the `mcp_gateway` section from `agents.yaml`.

## Data Flow

```
User Message
    ↓
Frontend (Next.js Server Action)
    ↓ POST /chats/{id}/messages (with bearer token from NextAuth session)
orchid-api (FastAPI)
    ↓ LangGraph.ainvoke()
    ├── Identity Resolution (bearer → OrchidAuthContext)
    ├── Supervisor Routing (match query to agent descriptions)
    ├── Agent 1 → RAG (Qdrant) → Tools (MCP/built-in) → LLM
    ├── Agent 2 → RAG → Tools → LLM
    └── Supervisor Synthesis → single AIMessage
    ↓ SSE stream (token-by-token)
Frontend → Browser (renders messages in real-time)
    ↓
Chat Storage (PostgreSQL/SQLite — persists for history)
```

## Deployment Order

1. **Infrastructure** — PostgreSQL, Qdrant, Ollama (if local). Start them and verify connectivity.
2. **Indexing** — Run the startup hook (or `orchid index`) to seed knowledge into Qdrant.
3. **API** — Start orchid-api. Verify `/health` returns `graph_ready: true`.
4. **Session Warm** — Call `POST /session/warm` to cache MCP capabilities.
5. **Frontend** — Start orchid-frontend. Verify chat creation and message sending.
6. **MCP Gateway** — Start orchid-mcp (optional). Verify tools appear in host LLM.
7. **Monitoring** — Enable LangSmith/OTEL. Verify traces appear in dashboards.

## Development vs. Production Configurations

### Development (Local, Minikube)

```yaml
llm:
  model: ollama/llama3.2           # Free, local
rag:
  vector_backend: chromadb          # Zero-infra
storage:
  class: orchid_ai.persistence.sqlite.OrchidSQLiteChatStorage
  dsn: /data/chats.db
auth:
  dev_bypass: true                  # No auth needed
tracing:
  langsmith_tracing: false
```

### Production (Cloud, Kubernetes)

```yaml
llm:
  model: openai/gpt-4o              # Cloud, high quality
  fallback_model: gemini/gemini-2.5-flash
rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant.cluster:6333
storage:
  class: orchid_ai.persistence.postgres.OrchidPostgresChatStorage
  dsn: postgresql+asyncpg://orchid:${DB_PASSWORD}@postgres:5432/orchid
auth:
  dev_bypass: false
  identity_resolver_class: myapp.identity.OIDCResolver
  oidc_issuer: https://auth.example.com
tracing:
  langsmith_tracing: true
  langsmith_api_key: ${LANGSMITH_API_KEY}
```
