# embedded-api — mount orchid-api into your existing FastAPI app

This example shows the **opposite direction** of `examples/api-extensions/`:
instead of adding custom endpoints to orchid-api's built-in app, you keep
YOUR existing FastAPI app and mount orchid's endpoints into it.

## When to use

- You already have a FastAPI app with your own routes, middleware, auth,
  and lifespan, and want to add an AI chat layer
- You want a single process / single deployment rather than running
  orchid-api as a separate service
- You need orchid endpoints namespaced under a prefix (e.g. `/ai/...`)

## How it works

`orchid_api` exports two building blocks:

```python
from orchid_api import setup_orchid, teardown_orchid
from orchid_api.routers import chats, messages, streaming, resume, sharing, legacy
```

`setup_orchid()` runs everything orchid-api needs (load config, build graph,
init storage, init checkpointer, run the startup hook, etc.). It populates
the shared `orchid_api.app_ctx` singleton that every router depends on.

`teardown_orchid()` closes connections, pools, and the checkpointer.

Each `router.router` is a `fastapi.APIRouter` — you include them with any
prefix you like.

## Example layout (`my_existing_app.py`)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from orchid_api import setup_orchid, teardown_orchid
from orchid_api.routers import chats, messages, streaming, resume

# your existing routers...
from .routes import products_router, orders_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Your own setup
    await my_db.connect()
    # Orchid setup
    await setup_orchid()
    yield
    # Teardown in reverse order
    await teardown_orchid()
    await my_db.disconnect()

app = FastAPI(title="My Business App", lifespan=lifespan)

# Your routes
app.include_router(products_router)
app.include_router(orders_router)

# Orchid routes, mounted under /ai
app.include_router(chats.router,     prefix="/ai")
app.include_router(messages.router,  prefix="/ai")
app.include_router(streaming.router, prefix="/ai")
app.include_router(resume.router,    prefix="/ai")
```

## Run the example

```bash
export GEMINI_API_KEY=your-key

ORCHID_CONFIG=examples/embedded-api/orchid.yml \
    uvicorn examples.embedded-api.my_existing_app:app --port 8000
```

## Try it

Your own app endpoints:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/products
curl http://localhost:8000/products/SKU-001
```

Orchid endpoints mounted under `/ai`:

```bash
# Create a chat
curl -X POST -H "Authorization: Bearer dev-token" \
    -H "Content-Type: application/json" \
    -d '{"title": "test"}' \
    http://localhost:8000/ai/chats

# List chats
curl -H "Authorization: Bearer dev-token" \
    http://localhost:8000/ai/chats

# Send a message (multipart)
curl -X POST -H "Authorization: Bearer dev-token" \
    -F "message=Hello" \
    http://localhost:8000/ai/chats/{chat_id}/messages
```

## What you can customise

- **Prefix** — use any prefix (e.g. `/v1/ai`, `/agents`, or no prefix at all)
- **Which routers** — include only the subset you need (e.g. skip `legacy.router` or `mcp_auth.router`)
- **Middleware, CORS** — use your own; orchid doesn't impose any on your app
- **Auth** — orchid's `Depends(get_auth_context)` reads the `Authorization` header.
  If you want the same token flow for both your app and orchid endpoints, that just works.
  If your app uses different auth, orchid's routers still honour their own flow.

## Caveats

- The entry-point **plugin system** (`[project.entry-points."orchid_api.routers"]`) only
  loads automatically when you run `orchid_api.main:app`. When embedding, you pick
  routers explicitly with `app.include_router()`.
- `orchid_api.app_ctx` is a module-level singleton — only one orchid instance per process.
  That's fine for embedding but means you can't run two differently-configured orchids
  in the same Python process.
- `setup_orchid()` must complete before any orchid route is called. Always put it in
  the FastAPI lifespan, never inline in a request handler.
