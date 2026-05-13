# api-extensions — custom FastAPI endpoints on orchid-api

Demonstrates **two patterns** integrators can use to add their own HTTP endpoints
to orchid-api without forking the framework:

| # | Pattern | When to use |
|---|---------|-------------|
| A | **Import & extend** — own `main.py` that imports `orchid_api.main.app` and calls `include_router` | Single deployment, no packaging |
| B | **Entry-point plugin** — declare `[project.entry-points."orchid_api.routers"]` in `pyproject.toml` | Reusable package installed into multiple deployments |

Both patterns expose the same endpoints (defined once in `routers/admin.py`):

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/admin/stats`           | Per-user/tenant usage stats |
| `POST` | `/admin/cache/clear`     | Reset the global LLM response cache |
| `POST` | `/admin/rag/index-text`  | On-demand RAG seeding |
| `GET`  | `/admin/agents`          | List loaded agents with config summary |

All endpoints use the same `get_auth_context` dependency as the built-in
routers, so your custom endpoints inherit the app's Bearer-token flow for free.

## Layout

```
examples/api-extensions/
├── README.md
├── orchid.yml             # shared config (reuses restaurant example)
├── pyproject.toml         # declares entry-point plugin (Pattern B)
├── custom_app.py          # Pattern A entry point
└── routers/
    └── admin.py           # the actual endpoints (FastAPI APIRouter)
```

## Pattern A — Import & extend

No installation required. Just run uvicorn with your own module:

```bash
export GEMINI_API_KEY=your-key
ORCHID_CONFIG=examples/api-extensions/orchid.yml \
    uvicorn examples.api-extensions.custom_app:app --port 8000
```

`custom_app.py` is 3 lines:

```python
from orchid_api.main import app
from .routers import admin
app.include_router(admin.router)
```

## Pattern B — Entry-point plugin (recommended)

Register your routers in `pyproject.toml` so they auto-load whenever
orchid-api starts:

```toml
[project.entry-points."orchid_api.routers"]
admin = "examples.api_extensions.routers.admin:router"
```

Install your package and run orchid-api as usual:

```bash
cd examples/api-extensions
pip install -e .

export GEMINI_API_KEY=your-key
ORCHID_CONFIG=examples/api-extensions/orchid.yml \
    uvicorn orchid_api.main:app --port 8000
```

On startup, orchid-api's `_load_router_plugins()` discovers the entry point,
imports the router, and calls `app.include_router(router)`. Failed plugins
log a warning but do not block startup.

## Try the endpoints

```bash
# Auth is bypassed (dev_bypass: true) — so dummy token is fine
export TOKEN="dev-token"

# Agent summary
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/agents

# Usage stats
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/stats

# Clear cache
curl -X POST -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/admin/cache/clear

# Seed RAG with an inline snippet
curl -X POST -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "content": "Our restaurant offers free WiFi password: GUEST2026",
        "namespace": "restaurant",
        "title": "WiFi info"
    }' \
    http://localhost:8000/admin/rag/index-text
```

## How the router accesses orchid-api internals

Consumer routers can freely import from `orchid_api`:

```python
from orchid_api.auth import get_auth_context   # same auth dependency
from orchid_api.context import app_ctx         # singleton: runtime, graph, storage
from orchid_api.settings import get_settings   # env-resolved config
```

Typical usage inside a custom endpoint:

```python
@router.get("/my-endpoint")
async def my_endpoint(auth: OrchidAuthContext = Depends(get_auth_context)):
    chat_repo = app_ctx.chat_repo                 # chat storage
    reader    = app_ctx.runtime.get_reader()      # vector store
    graph     = app_ctx.graph                     # compiled LangGraph
    mcp_store = app_ctx.mcp_token_store           # MCP OAuth tokens
    # ... do your thing ...
```

## Which pattern should I use?

- **Pattern A** is fastest to set up and ideal for a single deployment
  (one `uvicorn` command, no packaging).
- **Pattern B** is the right choice when multiple teams or deployments
  need to pull in the same custom endpoints — publish your package once,
  every orchid-api instance that installs it picks them up automatically.

You can also combine them: use Pattern A for dev-time experimentation,
then move the routers into a proper package with Pattern B once stable.
