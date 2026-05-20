<!-- Source: derived from orchid-api/README.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# Deployment

Guidelines for deploying the Orchid API server in production.

## Docker Deployment

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["uvicorn", "orchid_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
services:
  orchid-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ORCHID_CONFIG=/app/orchid.yml
      - QDRANT_URL=http://qdrant:6333
    volumes:
      - ./orchid.yml:/app/orchid.yml
      - ./data:/data
    depends_on:
      - qdrant
      - postgres

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: orchid
      POSTGRES_USER: orchid
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

## Uvicorn Configuration

```bash
uvicorn orchid_api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info \
  --timeout-keep-alive 65
```

### Workers

For multi-worker deployments:

- Use PostgreSQL (not SQLite) for storage.
- Each worker has its own LangGraph instance.
- Qdrant handles concurrent access natively.
- SSE connections are sticky (client stays on one worker).

## Environment Variables

```bash
# Required
ORCHID_CONFIG=path/to/orchid.yml

# LLM
LITELLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database
CHAT_DB_DSN=postgresql+asyncpg://user:pass@localhost:5432/orchid

# Vector Store
QDRANT_URL=http://qdrant:6333

# Auth
OIDC_ISSUER=https://auth.example.com
OIDC_CLIENT_ID=my-client
OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET}
```

## Multi-Tenancy

The API supports multi-tenancy through:

1. **Identity resolution** — `OrchidIdentityResolver` extracts `tenant_key` from tokens.
2. **RAG scoping** — Documents scoped per-tenant via `OrchidRAGScope`.
3. **Chat storage** — Chats filtered by `tenant_id`.
4. **MCP tokens** — Per-tenant per-user token stores.

## Health Checks

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "ok",
  "graph_ready": true,
  "db_connected": true,
  "qdrant_connected": true
}
```

## Logging

Configure structured logging:

```bash
LOG_LEVEL=info
LOG_FORMAT=json
```

Production logging includes:
- Request IDs for tracing.
- Agent invocation duration.
- MCP tool call latency.
- Error details (sanitized for PII).

## Security

- Run behind a reverse proxy (Nginx, Caddy) with TLS.
- Never expose the API directly to the internet.
- Use environment variables for secrets, never in YAML.
- Enable API key or OAuth for all endpoints.
- Set `dev_bypass: false` in production.
- Rotate API keys and secrets regularly.
