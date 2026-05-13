"""
Example: mount orchid-api into a pre-existing FastAPI application.

The integrator already has a FastAPI app with their own routes, middleware,
database, and lifespan.  They want to add the orchid agent/chat endpoints
as a sub-section of the app, without running a separate orchid-api process.

Run with::

    ORCHID_CONFIG=examples/embedded-api/orchid.yml \\
        uvicorn examples.embedded-api.my_existing_app:app --port 8000

Then hit either the existing app routes::

    GET  /products
    GET  /healthz

or the mounted orchid routes::

    POST /ai/chats
    GET  /ai/chats
    POST /ai/chats/{id}/messages
    POST /ai/chats/{id}/messages/stream
    POST /ai/chats/{id}/resume
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Orchid embedding: lifecycle + routers ──────────────────────
from orchid_api import setup_orchid, teardown_orchid
from orchid_api.routers import chats, legacy, messages, resume, sharing, streaming

logger = logging.getLogger(__name__)


# ── Pretend we have our own domain — a product catalogue ──────


class Product(BaseModel):
    sku: str
    name: str
    price_usd: float


_PRODUCTS = [
    Product(sku="SKU-001", name="Widget", price_usd=9.99),
    Product(sku="SKU-002", name="Gadget", price_usd=19.99),
    Product(sku="SKU-003", name="Gizmo", price_usd=29.99),
]

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.get("", response_model=list[Product])
def list_products() -> list[Product]:
    """The integrator's own business endpoint — lives alongside orchid's."""
    return _PRODUCTS


@products_router.get("/{sku}", response_model=Product | None)
def get_product(sku: str) -> Product | None:
    for p in _PRODUCTS:
        if p.sku == sku.upper():
            return p
    return None


# ── Lifespan: mix our setup with orchid setup ──────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Chain integrator setup with orchid setup."""
    # ── Integrator's own setup (db pool, cache, message bus, etc.) ──
    logger.info("[MyApp] Connecting to product DB (simulated)...")

    # ── Orchid's setup ──
    await setup_orchid()

    yield

    # ── Teardown: orchid first, then integrator resources ──
    await teardown_orchid()
    logger.info("[MyApp] Closing product DB connection (simulated)...")


# ── Build the app ──────────────────────────────────────────────


app = FastAPI(
    title="My Business App (with embedded Orchid AI)",
    version="1.0.0",
    lifespan=lifespan,
)

# Integrator's own middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Integrator's own routes ────────────────────────────────────
app.include_router(products_router)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "app": "my-business-app"}


# ── Orchid routes mounted under /ai ────────────────────────────
#
# You can include whichever subset you need — each is an APIRouter.
# Use a ``prefix`` to namespace them under your app's URL space.
ORCHID_PREFIX = "/ai"
app.include_router(chats.router, prefix=ORCHID_PREFIX)
app.include_router(messages.router, prefix=ORCHID_PREFIX)
app.include_router(streaming.router, prefix=ORCHID_PREFIX)
app.include_router(resume.router, prefix=ORCHID_PREFIX)
app.include_router(sharing.router, prefix=ORCHID_PREFIX)
app.include_router(legacy.router, prefix=ORCHID_PREFIX)
# Skipping mcp_auth.router here — enable it if your setup has OAuth-gated MCP servers.
