<!-- Source: derived from orchid-api/AGENTS.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# Embedding Patterns

The Orchid API can be embedded in an existing FastAPI application. Two patterns are supported for integrating Orchid with custom setups, each offering different levels of control and isolation.

## Pattern A: setup_orchid / teardown Functions

The simplest approach. Import and call the setup/teardown functions:

```python
from fastapi import FastAPI
from orchid_api.main import setup_orchid, teardown_orchid

app = FastAPI()
app.include_router(my_custom_router)  # Your own routers first

@app.on_event("startup")
async def startup():
    await setup_orchid(app)
    # Orchid routers are now mounted

@app.on_event("shutdown")
async def shutdown():
    await teardown_orchid()
```

`setup_orchid()` handles:
- Loading `orchid.yml` configuration.
- Initializing chat storage (SQLite or PostgreSQL with migration).
- Building the vector reader (Qdrant or null).
- Compiling the LangGraph.
- Running startup hooks (seed knowledge, warm MCP capabilities).
- Mounting all Orchid routers (`/chats`, `/messages`, `/streaming`, `/auth`, etc.).

Use this when you want the full Orchid API surface in your application with minimal configuration.

## Pattern B: Lifespan Context Manager

Uses FastAPI's modern lifespan context manager (recommended for FastAPI 0.95+):

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from orchid_api.main import setup_orchid, teardown_orchid

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await setup_orchid(app)
    yield
    # Shutdown
    await teardown_orchid()

app = FastAPI(lifespan=lifespan)
```

This pattern is cleaner because it keeps startup and shutdown logic together in one place.

## Custom Integration (Manual Control)

For full control over which Orchid components are mounted:

```python
from fastapi import FastAPI
from orchid_api.routers import chats, messages, streaming
from orchid_api.context import app_ctx

app = FastAPI()

# Initialize Orchid context manually
await app_ctx.initialize(config_path="orchid.yml")

# Mount only the routers you need, with custom prefixes
app.include_router(chats.router, prefix="/api/v2/orchid")
app.include_router(messages.router, prefix="/api/v2/orchid")
app.include_router(streaming.router, prefix="/api/v2/orchid")
# Don't mount admin, auth, or sharing routers
```

Use this when you want selective Orchid endpoints, custom URL prefixes, or you need to intercept/modify requests before they reach Orchid routers.

## Middleware Integration

Add custom middleware alongside Orchid:

```python
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# CORS — allow your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://myapp.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom auth middleware
class TenantExtractionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Extract tenant from subdomain
        tenant = request.headers.get("host", "").split(".")[0]
        request.state.tenant = tenant
        return await call_next(request)

app.add_middleware(TenantExtractionMiddleware)
```

Middleware order matters — CORS should be first, followed by auth, then custom middleware.

## Environment Variables for Embedded Deployments

Key environment variables when embedding:

```bash
# Orchid configuration
ORCHID_CONFIG=/etc/myapp/orchid.yml
AGENTS_CONFIG_PATH=/etc/myapp/agents.yaml

# Storage
CHAT_DB_DSN=postgresql+asyncpg://orchid:${DB_PASS}@postgres:5432/orchid

# Vector Store
QDRANT_URL=http://qdrant:6333

# LLM
LITELLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=${OPENAI_API_KEY}

# Upload
UPLOAD_MAX_SIZE_MB=20

# Auth
AUTH_DEV_BYPASS=false
IDENTITY_RESOLVER_CLASS=myapp.identity.OIDCResolver
```

## Custom Error Handlers

Add error handlers for Orchid-specific exceptions:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(OrchidAgentNotFoundError)
async def agent_not_found_handler(request: Request, exc: OrchidAgentNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": f"Agent '{exc.agent_name}' not found"},
    )
```

## Testing the Embedded API

Test the embedded API with FastAPI's TestClient:

```python
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["graph_ready"] is True
```
