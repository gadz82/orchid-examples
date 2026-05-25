# PostgreSQL Storage Example

Demonstrates the **`orchid-storage-postgres`** plugin for production-grade PostgreSQL persistence:

- **Chat storage** — `OrchidPostgresChatStorage` (asyncpg connection pooling)
- **Checkpointer** — PostgreSQL checkpointer bundled in the plugin (LangGraph state persistence across agent turns)
- **Visibility fragment** — Plugin auto-registers the postgres `$1..$N` visibility filter (no YAML needed)
- **Qdrant RAG** — Vector search via the `orchid-rag-qdrant` plugin

## What It Demonstrates

| Feature | Configuration |
|---------|--------------|
| Chat storage | `orchid_storage_postgres.OrchidPostgresChatStorage` |
| Checkpointer | PostgreSQL (bundled in orchid-storage-postgres) |
| Visibility | Auto-registered postgres fragment |
| RAG | Qdrant vector backend via orchid-rag-qdrant |
| LLM | Ollama (`llama3.2`, `nomic-embed-text`) |
| Agents | `echo` + `reverse` (cross-agent skill routing) |

## Architecture

```
┌──────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  User Chat   │────▶│  Orchid Graph   │────▶│  PostgreSQL DB   │
│  (HTTP/CLI)  │     │  (supervisor)   │     │  (chat storage + │
└──────────────┘     └─────────────────┘     │   checkpointer)  │
                            │                 └──────────────────┘
                            ▼
                    ┌──────────────────┐
                    │  Qdrant          │
                    │  (vector search) │
                    └──────────────────┘
```

## Prerequisites

- Ollama running with models:
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ```
- Docker (for PostgreSQL and Qdrant services)
- Python 3.11+ with `orchid-ai`, `orchid-api`, and plugins installed

## Usage

### Via Docker Compose (Recommended)

```bash
# From repo root — starts API + PostgreSQL + Qdrant
script/start_postgres_storage.sh

# Or manually:
ORCHID_CONFIG=examples/postgres-storage/orchid.yml \
docker compose -f script/docker-compose.examples.yml \
  --profile postgres --profile qdrant up --build
```

### Via Standalone API

```bash
# Start PostgreSQL locally first
docker run -d --name postgres-echo -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=orchid \
  postgres:16-alpine

# Run the API
ORCHID_CONFIG=examples/postgres-storage/orchid.yml \
POSTGRES_PASSWORD=postgres \
  uvicorn orchid_api.main:app --port 8000
```

### Via CLI

```bash
POSTGRES_PASSWORD=postgres \
orchid chat interactive --config examples/postgres-storage/orchid.yml
```

## Plugin Dependencies

This example requires two Orchid plugins:

```bash
pip install orchid-storage-postgres orchid-rag-qdrant
```

Both auto-register via `importlib.metadata` entry points — no manual setup needed.

## Verifying PostgreSQL Backend

After sending a few messages, connect to PostgreSQL to verify persistence:

```bash
docker exec -it postgres psql -U postgres -d orchid

# Check chat sessions
SELECT id, title, tenant_key, user_id, created_at FROM chat_sessions;

# Check message count
SELECT session_id, count(*) AS messages FROM chat_messages GROUP BY session_id;

# Check LangGraph checkpoints
SELECT count(*) FROM checkpoints;
```

## Cleanup

```bash
docker rm -f postgres
docker volume rm orchid-examples_pgdata
```
