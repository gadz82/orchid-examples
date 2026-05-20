<!-- Source: derived from orchid-api/AGENTS.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# Extensions

The Orchid API supports plugin discovery and custom extension points, allowing integrators to add custom routers, middleware, and hooks without modifying the framework code.

## Plugin Discovery

The API scans for plugins at startup using an automatic discovery mechanism. Plugins are Python packages that follow a convention — typically exposing a `router` object and optional `setup()` / `teardown()` hooks. The discovery mechanism finds these packages and mounts them during the FastAPI lifespan.

### Plugin Structure

A plugin package typically looks like:

```
my_plugin/
├── __init__.py
├── router.py          # FastAPI APIRouter
├── middleware.py       # Optional: Starlette middleware
└── hooks.py           # Optional: startup/shutdown hooks
```

## Custom Routers

Plugins register routers that are mounted alongside built-in routers:

```python
# my_plugin/router.py
from fastapi import APIRouter

router = APIRouter(prefix="/custom", tags=["custom"])

@router.get("/status")
async def custom_status():
    return {"custom": "ok", "plugins": ["my-plugin"]}

@router.post("/action")
async def custom_action(payload: dict):
    result = await process_action(payload)
    return {"result": result}
```

The API discovers this router at startup and mounts it:

```python
# API mounts custom routers automatically
app.include_router(custom_router)
```

### URL Prefixing

Custom routers can use any prefix. Avoid colliding with built-in prefixes (`/chats`, `/auth`, `/admin`, `/index`, `/health`, `/mcp-gateway`).

## Middleware Extensions

Plugins can add Starlette middleware to the API:

```python
# my_plugin/middleware.py
from starlette.middleware.base import BaseHTTPMiddleware

class RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        response.headers["X-Request-Duration"] = str(duration)
        return response

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if await self._is_rate_limited(request):
            return JSONResponse(
                {"error": "rate_limited"}, status_code=429
            )
        return await call_next(request)
```

Middleware runs in the order it's registered. Built-in middleware (CORS, auth) runs first, then plugin middleware.

## Startup Hooks

Extensions can register startup hooks that run during API initialization:

```yaml
# orchid.yml
startup:
  hook: myapp.hooks.my_custom_startup
```

The hook function receives the compiled graph, reader, and settings:

```python
# myapp/hooks.py
async def my_custom_startup(reader, settings, **kwargs):
    """Custom initialization that runs after the graph is built."""
    # Seed custom data
    # Register custom tools
    # Validate external connections
    logger.info("Custom startup hook completed")
```

Multiple hooks can be registered and run sequentially.

## Admin Endpoints

Extensions can add custom admin endpoints for operational tasks:

```python
@router.post("/admin/clear-cache")
async def clear_cache():
    await cache.clear()
    return {"status": "cache cleared"}

@router.get("/admin/stats")
async def custom_stats():
    return {
        "active_users": await get_active_users(),
        "total_chats": await get_total_chats(),
        "cache_size_mb": get_cache_size(),
    }
```

These are mounted under `/admin` alongside built-in admin endpoints.

## Error Handling

If a plugin fails to load:
- The API logs a warning with the plugin name and error details.
- The API continues with remaining plugins.
- A failing plugin never crashes the entire API.

### Debug Plugin Loading

```bash
LOG_LEVEL=DEBUG uvicorn orchid_api.main:app
# Shows: "Discovered plugin: my-plugin", "Loading plugin: my-plugin", "Plugin loaded: my-plugin"
# Or: "Plugin failed to load: my-plugin — ImportError: No module named 'missing_dep'"
```

## Extension Best Practices

- **Lazy initialization** — Plugins should not depend on import order. Use lazy initialization for heavy dependencies.
- **Graceful degradation** — Handle missing dependencies with clear error messages.
- **Log registration** — Log at startup when plugins are registered.
- **Isolation** — Test plugins in isolation before deploying with the full API.
- **Versioning** — Pin plugin dependencies to avoid compatibility issues.
- **No framework modifications** — Plugins extend via public APIs only; don't monkey-patch framework internals.
