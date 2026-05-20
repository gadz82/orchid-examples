<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid-website/src/content/ecosystem.mdx, and codebase analysis -->

# Production Architecture

Guidelines for deploying the full Orchid stack in production.

## Full-Stack Deployment

```
                        ┌─────────────────┐
                        │   MCP Gateway    │
                        │  (orchid-mcp)    │
                        └────────┬────────┘
                                 │ HTTP
┌──────────┐    HTTPS    ┌───────▼────────┐    gRPC/REST   ┌─────────┐
│  Browser  │────────────▶│   Orchid API   │◀──────────────│  Qdrant  │
│ (Next.js) │◀────────────│  (FastAPI)     │               │ (Vector) │
└──────────┘    SSE       └───────┬────────┘               └─────────┘
                                  │
                           ┌──────▼────────┐
                           │   PostgreSQL   │
                           │  (Storage)     │
                           └───────────────┘
```

## Component Roles

| Component | Role | Scale |
|-----------|------|-------|
| `orchid-frontend` | User-facing chat UI | Horizontal (stateless) |
| `orchid-api` | Graph execution, RAG, streaming | Horizontal (stateless with PostgreSQL) |
| `orchid-mcp` | MCP gateway for external hosts | Horizontal (stateless) |
| Qdrant | Vector storage and retrieval | Horizontal (cluster mode) |
| PostgreSQL | Chat storage, tokens, events | Vertical or cluster |
| Ollama | Local LLM inference | Single node (GPU) |

## Infrastructure Patterns

### Docker Compose (Small)

For demos and small deployments:

```yaml
services:
  frontend: ...  # Next.js
  api: ...        # FastAPI
  qdrant: ...     # Vector store
  postgres: ...   # Database
  ollama: ...     # LLM (optional)
```

### Kubernetes (Production)

For production with auto-scaling:

```
Deployment: frontend (2-4 replicas)
Deployment: api (2-4 replicas)
StatefulSet: qdrant (3 replicas, cluster)
StatefulSet: postgres (primary + replicas)
Deployment: mcp-gateway (2 replicas)
```

## Network Architecture

```
Internet → TLS (Load Balancer) → Frontend (Next.js)
                                  │
                                  ▼
           Internal Network → API (FastAPI)
                                  │
                          ┌───────┼───────┐
                          ▼       ▼       ▼
                      Qdrant  Postgres  MCP Servers
```

- **Frontend** — Public, serves static assets and proxies API calls.
- **API** — Internal, accessed only by frontend and MCP gateway.
- **Data stores** — Internal, accessed only by API.

## Secrets Management

- `.env` files for local development (gitignored).
- Environment variables for Docker deployments.
- Secrets manager (Vault, AWS Secrets Manager, GCP Secret Manager) for production.
- Never commit credentials, API keys, or tokens to version control.

## Monitoring

- **Health checks** — `/health` endpoint for API, liveness probes for all services.
- **Logging** — Structured JSON logs with correlation IDs.
- **Metrics** — Request latency, error rates, agent invocation counts.
- **Tracing** — LangSmith or OpenTelemetry for distributed tracing.
- **Alerting** — High error rates, high latency, storage capacity warnings.
