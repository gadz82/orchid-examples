<!-- Source: derived from orchid-website/src/content/best-practices.mdx and codebase analysis -->

# Scaling

Guidelines for scaling Orchid deployments horizontally and managing state in multi-replica environments.

## Horizontal Scaling

### Stateless Components (Scale Horizontally)

- **Frontend (Next.js)** — Fully stateless, scale to N replicas.
- **API (FastAPI)** — Stateless with PostgreSQL, scale to N replicas.
- **MCP Gateway (orchid-mcp)** — Stateless with token stores, scale to N replicas.

### Stateful Components (Scale Carefully)

- **Qdrant** — Cluster mode with Raft consensus (3+ nodes recommended).
- **PostgreSQL** — Primary + replicas, or managed service (RDS, Cloud SQL).
- **Ollama** — Single node (GPU). Use cloud providers for multi-node LLM inference.

## API Replica Considerations

### SSE Sticky Sessions

SSE connections must be sticky in multi-replica deployments:

```nginx
upstream api_backend {
    ip_hash;  # Sticky sessions by client IP
    server api-1:8000;
    server api-2:8000;
}
```

Without sticky sessions, SSE connections may bounce between replicas.

### Shared State

Replicas share state via:
- **PostgreSQL** — Chat storage, token stores (ACID, concurrent-safe).
- **Qdrant** — Vector storage (cluster mode, concurrent-safe).
- **No in-memory state** — Replicas must not rely on in-memory state for correctness.

### Graceful Shutdown

API replicas should handle graceful shutdown:

```python
@app.on_event("shutdown")
async def shutdown():
    await app_ctx.close()    # Close DB connections
    await reader.close()     # Close vector connections
```

## Gateway Patterns

### API Gateway

Use a reverse proxy (Nginx, Caddy, Traefik) as the entry point:

```
Internet → API Gateway (TLS) → Frontend (Next.js)
                              → API (FastAPI)
                              → MCP Gateway (orchid-mcp)
```

### Load Balancing

- **Round-robin** — For stateless HTTP requests.
- **Sticky sessions** — For SSE connections.
- **Health checks** — Remove unhealthy replicas.

## Capacity Planning

### Qdrant

- **Memory** — Vector index fits in memory for best performance. Rule of thumb: 1GB RAM per 1M vectors (at 768 dimensions).
- **Storage** — 1M vectors ≈ 3-6GB disk (dense) or 1-2GB (sparse).

### PostgreSQL

- **Connections** — Use PgBouncer for connection pooling if >100 concurrent API connections.
- **Storage** — Chat history grows linearly. Estimate ~1KB per message.

### API

- **CPU** — LLM calls are I/O bound (waiting for provider). Light CPU usage for graph execution.
- **Memory** — ~200MB per replica + vector store cache.
- **Concurrency** — Limited by LLM provider rate limits, not API capacity.

## Monitoring at Scale

- Track replica count and health.
- Monitor database connection pools.
- Set alerts on Qdrant memory usage.
- Monitor SSE connection counts.
- Track token usage and costs per tenant.
