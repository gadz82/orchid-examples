"""
Admin router — demonstrates custom endpoints added to orchid-api.

Provides:
  GET  /admin/stats             — aggregate usage stats
  POST /admin/cache/clear       — clear the global LLM response cache
  POST /admin/rag/index-text    — on-demand RAG seeding from request body
  GET  /admin/agents            — list loaded agents with their configs

All endpoints require authentication and accept the same Bearer token used
by the rest of the API.  This shows how consumer code can:
  - Access the singleton ``app_ctx`` to reach runtime, graph, storage
  - Use the same ``get_auth_context`` dependency for consistent auth
  - Declare Pydantic request/response models
  - Work with ``OrchidVectorWriter`` for dynamic RAG seeding
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from orchid_ai.core.repository import Document, OrchidVectorWriter
from orchid_ai.core.state import OrchidAuthContext

# orchid-api internals — consumers can import these directly
from orchid_api.auth import get_auth_context
from orchid_api.context import app_ctx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Models ────────────────────────────────────────────────────


class StatsResponse(BaseModel):
    tenant_id: str
    user_id: str
    total_chats: int
    total_messages: int
    agents: list[str]
    has_checkpointer: bool
    has_vector_backend: bool


class IndexTextRequest(BaseModel):
    content: str
    namespace: str
    doc_id: str | None = None
    title: str | None = None


class IndexTextResponse(BaseModel):
    status: str
    doc_id: str
    namespace: str
    tenant_id: str


class CacheClearResponse(BaseModel):
    status: str
    message: str


class AgentInfo(BaseModel):
    name: str
    description: str
    rag_namespace: str
    tool_count: int
    has_approval_tools: bool


class AgentsResponse(BaseModel):
    count: int
    agents: list[AgentInfo]


# ── Endpoints ─────────────────────────────────────────────────


@router.get("/stats", response_model=StatsResponse)
async def get_stats(auth: OrchidAuthContext = Depends(get_auth_context)) -> StatsResponse:
    """Return usage stats scoped to the authenticated user + tenant."""
    if app_ctx.chat_repo is None:
        raise HTTPException(status_code=503, detail="Chat storage not initialised")

    chats = await app_ctx.chat_repo.list_chats(tenant_id=auth.tenant_key, user_id=auth.user_id)
    total_messages = 0
    for chat in chats:
        msgs = await app_ctx.chat_repo.get_messages(chat.id, limit=10000)
        total_messages += len(msgs)

    # Agent names from the compiled graph
    agents: list[str] = []
    if app_ctx.graph is not None:
        try:
            agents = sorted(
                n for n in app_ctx.graph.nodes if n.endswith("_agent")
            )
            agents = [a.removesuffix("_agent") for a in agents]
        except Exception:
            pass

    return StatsResponse(
        tenant_id=auth.tenant_key,
        user_id=auth.user_id,
        total_chats=len(chats),
        total_messages=total_messages,
        agents=agents,
        has_checkpointer=app_ctx.runtime.checkpointer is not None,
        has_vector_backend=app_ctx.runtime.reader is not None,
    )


@router.post("/cache/clear", response_model=CacheClearResponse)
async def clear_cache(auth: OrchidAuthContext = Depends(get_auth_context)) -> CacheClearResponse:
    """Clear the global LangChain LLM response cache."""
    try:
        from langchain_core.caches import InMemoryCache
        from langchain_core.globals import get_llm_cache, set_llm_cache

        current = get_llm_cache()
        if current is None:
            return CacheClearResponse(status="noop", message="No cache configured")

        # Reset the cache in-place (idiomatic way: replace with fresh InMemoryCache)
        set_llm_cache(InMemoryCache())
        logger.info("[Admin] User %s cleared LLM response cache", auth.user_id)
        return CacheClearResponse(status="ok", message="LLM response cache cleared")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {exc}") from exc


@router.post("/rag/index-text", response_model=IndexTextResponse)
async def index_text(
    body: IndexTextRequest,
    auth: OrchidAuthContext = Depends(get_auth_context),
) -> IndexTextResponse:
    """Index an inline text snippet into a vector namespace.

    The document is scoped to the caller's tenant and stored with an
    idempotent content-hashed ID.  Re-indexing the same text is a no-op.
    """
    reader = app_ctx.runtime.get_reader()
    if not isinstance(reader, OrchidVectorWriter):
        raise HTTPException(status_code=503, detail="Vector backend does not support writing")

    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Empty content")

    doc_id = body.doc_id or f"admin-{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    metadata: dict[str, Any] = {
        "tenant_id": auth.tenant_key,
        "scope": "tenant",
        "source": "admin-api",
        "indexed_by": auth.user_id,
    }
    if body.title:
        metadata["title"] = body.title

    doc = Document(id=doc_id, page_content=content, metadata=metadata)
    await reader.upsert([doc], body.namespace)

    logger.info(
        "[Admin] User %s indexed text doc '%s' into namespace '%s'",
        auth.user_id, doc_id, body.namespace,
    )
    return IndexTextResponse(
        status="ok",
        doc_id=doc_id,
        namespace=body.namespace,
        tenant_id=auth.tenant_key,
    )


@router.get("/agents", response_model=AgentsResponse)
async def list_agents(auth: OrchidAuthContext = Depends(get_auth_context)) -> AgentsResponse:
    """List all loaded agents with their configuration summary."""
    # Re-read the loaded config from settings to avoid reaching into graph internals
    from orchid_ai.config.loader import load_config

    from orchid_api.settings import get_settings

    settings = get_settings()
    try:
        agents_config = load_config(settings.agents_config_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cannot load agents config: {exc}") from exc

    agents = []
    for name, cfg in agents_config.agents.items():
        mcp_tool_count = sum(len(s.tools) for s in cfg.mcp_servers)
        tool_count = len(cfg.tools) + mcp_tool_count
        agents.append(AgentInfo(
            name=name,
            description=cfg.description[:120],
            rag_namespace=cfg.rag.namespace,
            tool_count=tool_count,
            has_approval_tools=bool(cfg.approval_tools),
        ))

    return AgentsResponse(count=len(agents), agents=agents)
