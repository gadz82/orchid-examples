<!-- Source: derived from orchid-api/AGENTS.md, orchid-api/README.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# Architecture

`orchid-api` is the FastAPI HTTP server that wraps the Orchid framework library. It provides the REST API and SSE streaming that the frontend, CLI, and MCP gateway consume.

## App Factory Pattern

The application is built via a factory function that assembles all routers, middleware, and lifecycle hooks:

```python
# orchid_api/main.py
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="Orchid API", lifespan=lifespan)
    app.include_router(chats.router)
    app.include_router(messages.router)
    # ... more routers
    return app

app = create_app()
```

## AppContext Singleton

**File:** `orchid_api/context.py`

`AppContext` holds all runtime state - the compiled LangGraph, chat storage, vector reader, MCP clients - and is accessible to all routers:

```python
from ..context import app_ctx

@app.get("/health")
async def health():
    return {"status": "ok", "graph_ready": app_ctx.graph is not None}
```

No module-level globals (other than the context singleton). Routers access dependencies via `app_ctx`.

## Lifespan

The FastAPI lifespan hook manages startup and shutdown:

### Startup
1. Load `orchid.yml` configuration.
2. Resolve `identity_resolver_class` via `importlib`.
3. Initialize chat storage (SQLite or PostgreSQL).
4. Build the vector reader (Qdrant or null).
5. Run startup hooks (seed knowledge, warm MCP capabilities).
6. Compile the LangGraph.

### Shutdown
1. Close chat storage connections.
2. Close vector reader connections.
3. Stop event processors (if Pollen+Bloom enabled).

## Router Map

Routers are split by domain:

| Router | File | Purpose |
|--------|------|---------|
| `chats` | `routers/chats.py` | Chat CRUD (create, list, get, delete, update title) |
| `messages` | `routers/messages.py` | Message send + multipart file upload |
| `streaming` | `routers/streaming.py` | SSE streaming for chat and bloom |
| `sharing` | `routers/sharing.py` | Chat sharing between users |
| `resume` | `routers/resume.py` | Resume existing chats |
| `mcp_auth` | `routers/mcp_auth.py` | MCP gateway OAuth endpoints |
| `admin` | `routers/admin.py` | `/index` endpoint for RAG indexing |
| `diagnostics` | `routers/diagnostics.py` | `/health` and status endpoints |

## Settings

**File:** `orchid_api/settings.py`

All configuration from `orchid.yml` and environment variables, with defaults.

## Auth

**File:** `orchid_api/auth.py`

Identity resolution: the API calls `OrchidIdentityResolver.resolve()` on every request to produce an `OrchidAuthContext` for the graph.

## Dependency Direction

```
orchid-api/ → orchid/    (framework library)
orchid-api/ → FastAPI    (web framework)
```

The API depends on the framework library but the framework has no FastAPI dependency.
