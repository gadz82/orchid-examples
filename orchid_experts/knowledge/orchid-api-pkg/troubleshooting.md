<!-- Source: derived from orchid-api/AGENTS.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# Troubleshooting

Common deployment issues with the Orchid API server and their solutions.

## CORS Errors

Frontend can't connect to the API:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Ensure the frontend origin is in the allowed origins list.

## Embedding Dimension Mismatch

Qdrant returns errors about vector dimensions:

```
Error: Vector dimension 768 does not match collection dimension 1536
```

**Cause:** Switched embedding models without re-indexing.

**Fix:** Delete the Qdrant collection and re-index:

```bash
curl -X DELETE http://localhost:6333/collections/my_namespace
# Restart the API to re-index
```

## Graph Not Ready

Health check returns `graph_ready: false`:

**Cause:** Configuration error during startup. Check logs for:
- Invalid `agents.yaml` (Pydantic validation errors).
- Missing identity resolver class.
- Database connection errors.

## Multipart Upload Issues

File uploads fail with 413:

**Cause:** File exceeds `max_size_mb` limit.

**Fix:** Increase the limit in `orchid.yml`:

```yaml
upload:
  max_size_mb: 50
```

## Ollama Connection

Agents return errors about Ollama:

**Cause:** Ollama not running or wrong API base.

**Fix:** 
1. Ensure Ollama is running: `ollama serve`
2. Check the API base in `orchid.yml`:

```yaml
llm:
  ollama_api_base: http://host.docker.internal:11434  # Docker
  # or http://localhost:11434  # Local
```

## Database Migration Errors

Startup fails with migration errors:

**Cause:** Database schema changes require migration.

**Fix:** Delete the database and restart (development only):

```bash
rm /data/chats.db
# Restart — migrations run automatically
```

For production, manage migrations carefully.

## SSE Connection Drops

Streaming connections drop frequently:

**Causes:**
- Reverse proxy timeout (Nginx, load balancer).
- Client disconnection.

**Fixes:**
- Increase proxy timeouts.
- Implement client reconnection logic.
- Check for network issues.

## Memory Issues

API uses excessive memory:

**Causes:**
- Too many concurrent SSE connections.
- Large vector store in memory (ChromaDB).
- Large conversation histories.

**Fixes:**
- Enable history summarization (`history_summary_enabled: true`).
- Use Qdrant instead of ChromaDB for large deployments.
- Limit concurrent connections in the reverse proxy.
