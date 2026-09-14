"""Auto-loaded shared fixtures for Orchid example e2e tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from examples._e2e_shared.fixtures import *
from examples._e2e_shared.fixtures.auth import (
    DEFAULT_TOKEN,
)

# ── SQLite helper ─────────────────────────────────────────────


@pytest.fixture
async def tmp_sqlite_db(tmp_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    """Temporary SQLite connection with WAL and foreign keys enabled."""
    dsn = str(tmp_path / "test.db")
    conn = await aiosqlite.connect(dsn)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    await conn.close()


# ── Live-server HTTP client ───────────────────────────────────


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client for live-server tests.

    Points at ``ORCHID_API_URL`` (default ``http://localhost:8080``).
    """
    base_url = os.environ.get("ORCHID_API_URL", "http://localhost:8080")
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        yield client


# ── In-process orchid-api app builder ─────────────────────────


@asynccontextmanager
async def build_orchid_test_app(
    *,
    example: str | Path | None = None,
    vector_store: Any = None,
    chat_model: Any = None,
    mcp_client_factory: Any = None,
    extra_env: dict[str, str] | None = None,
    include_event_router: bool = False,
) -> AsyncIterator[TestClient]:
    """Build a fresh orchid-api TestClient for an example.

    Parameters
    ----------
    example
        Example name (e.g. ``"basketball"``) or path to its directory.
        When ``None``, a minimal empty config is used.
    vector_store
        Optional :class:`examples._e2e_shared.fixtures.InMemoryVectorStore`
        to inject into the runtime.
    chat_model
        Optional LangChain chat model to inject into the runtime.
    mcp_client_factory
        Optional MCP client factory to inject into the runtime.
    extra_env
        Extra environment variables to set during setup.
    include_event_router
        Whether to mount the HTTPIngestionProducer router if events are
        enabled. The producer itself must be attached to app_ctx.events.
    """
    import shutil

    from orchid_api.context import app_ctx
    from orchid_api.lifecycle import setup_orchid, teardown_orchid
    from orchid_api.routers import (
        admin,
        auth_exchange,
        auth_identity,
        auth_info,
        chat_events,
        chats,
        diagnostics,
        jobs,
        mcp_auth,
        mcp_gateway,
        mcp_gateway_state,
        messages,
        resume,
        runs,
        schedules,
        session,
        sharing,
        signals,
        streaming,
    )

    examples_root = Path(__file__).resolve().parents[1]
    if example is None:
        example_dir = examples_root / "_e2e_shared" / "data" / "minimal-example"
    elif isinstance(example, str):
        example_dir = examples_root / example
    else:
        example_dir = example

    orchid_yml = example_dir / "orchid.yml"
    if not orchid_yml.exists():
        orchid_yml = example_dir / "orchid.md"

    # The md-config example ships both orchid.yml (fallback) and
    # orchid.md (the feature under test).  Prefer the Markdown config
    # when it exists alongside a YAML fallback so the e2e suite
    # exercises the MD loader.
    if (example_dir / "orchid.md").exists() and (example_dir / "agents").exists():
        md_files = list((example_dir / "agents").glob("*.md"))
        if md_files:
            orchid_yml = example_dir / "orchid.md"

    # Prepare a temp directory for all DBs/checkpoints/exports.
    tmp_root = Path(tempfile.mkdtemp(prefix="orchid-e2e-"))

    old_environ = dict(os.environ)
    env_overrides: dict[str, str] = {
        "ORCHID_CONFIG": str(orchid_yml),
        "DEV_AUTH_BYPASS": "true",
        "DEV_BYPASS_TOKEN": DEFAULT_TOKEN,
        "CHAT_DB_DSN": str(tmp_root / "chats.db"),
        "MCP_TOKEN_STORE_DSN": str(tmp_root / "chats.db"),
        "MCP_CLIENT_REGISTRATION_STORE_DSN": str(tmp_root / "chats.db"),
        "MCP_GATEWAY_STATE_STORE_DSN": str(tmp_root / "chats.db"),
        "ORCHID_EVENTS_DSN": str(tmp_root / "events.db"),
        "CHECKPOINTER_TYPE": "sqlite",
        "CHECKPOINTER_DSN": str(tmp_root / "checkpoints.db"),
        "ORCHID_EXPORT_DIR": str(tmp_root / "exports"),
        "VECTOR_BACKEND": "null",
        "CHAT_STORAGE_CLASS": "orchid_ai.persistence.sqlite.OrchidSQLiteChatStorage",
        "LANGSMITH_TRACING": "false",
        "ORCHID_ENABLE_PERF_LOGS": "false",
        "RATE_LIMIT_MESSAGES_PER_MINUTE": "0",
        "RATE_LIMIT_UPLOADS_PER_MINUTE": "0",
        "RATE_LIMIT_INDEX_PER_MINUTE": "0",
    }
    if extra_env:
        env_overrides.update(extra_env)

    # Markdown configs do not run env-variable interpolation in their
    # frontmatter, so hardcoded /data/... DSNs would be read-only in
    # tests.  Create a temp copy of the root .md file with DSNs
    # redirected into tmp_root and copy the agents directory so the
    # MD loader resolves relative paths correctly.
    if orchid_yml.suffix == ".md":
        md_text = orchid_yml.read_text(encoding="utf-8")
        md_text = md_text.replace("dsn: /data/chats.db", f"dsn: {tmp_root / 'chats.db'}")
        md_text = md_text.replace("dsn: /data/events.db", f"dsn: {tmp_root / 'events.db'}")
        tmp_md = tmp_root / "orchid.md"
        tmp_md.write_text(md_text, encoding="utf-8")
        original_agents = orchid_yml.parent / "agents"
        if original_agents.exists():
            import shutil
            shutil.copytree(original_agents, tmp_root / "agents")
        orchid_yml = tmp_md
        env_overrides["ORCHID_CONFIG"] = str(orchid_yml)
        # Markdown configs resolve agents from the frontmatter agents_dir;
        # AGENTS_CONFIG_PATH must not override it.
        env_overrides["AGENTS_CONFIG_PATH"] = ""
    else:
        env_overrides["AGENTS_CONFIG_PATH"] = str(example_dir / "agents.yaml")

    # Clear any stale app_ctx state.
    await app_ctx.release_resources()

    client: TestClient | None = None
    try:
        os.environ.update(env_overrides)

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Inject test doubles into OrchidRuntime BEFORE setup_orchid()
            # builds the graph, so agents, RAG pipelines, and the supervisor
            # all see the same fakes.
            original_from_config_path: Any = None
            original_build_chat_model: Any = None
            needs_patch = chat_model is not None or vector_store is not None or mcp_client_factory is not None
            if needs_patch:
                from orchid_ai.orchid.orchid import Orchid

                original_from_config_path = Orchid.from_config_path

                @classmethod
                async def _patched_from_config_path(cls, *args: Any, **kwargs: Any):
                    runtime_overrides = kwargs.get("runtime_overrides") or {}
                    if chat_model is not None:
                        runtime_overrides["chat_model"] = chat_model
                    if vector_store is not None:
                        runtime_overrides["reader"] = vector_store.repository()
                    if mcp_client_factory is not None:
                        runtime_overrides["mcp_client_factory"] = mcp_client_factory
                    kwargs["runtime_overrides"] = runtime_overrides
                    return await original_from_config_path(*args, **kwargs)

                Orchid.from_config_path = _patched_from_config_path

            if chat_model is not None:
                # Also patch the low-level factory so agents whose YAML
                # ``llm.model`` differs from the runtime default don't
                # bypass the injected fake model.
                import orchid_ai.llm_factory as _llm_factory

                original_build_chat_model = _llm_factory.build_chat_model

                def _patched_build_chat_model(model_name: str, **kwargs: Any):
                    return chat_model

                _llm_factory.build_chat_model = _patched_build_chat_model

            try:
                await setup_orchid()
            finally:
                if original_from_config_path is not None:
                    from orchid_ai.orchid.orchid import Orchid

                    Orchid.from_config_path = original_from_config_path
                if original_build_chat_model is not None:
                    import orchid_ai.llm_factory as _llm_factory

                    _llm_factory.build_chat_model = original_build_chat_model

            yield
            await teardown_orchid()

        app = FastAPI(lifespan=lifespan)
        app.include_router(chats.router)
        app.include_router(messages.router)
        app.include_router(resume.router)
        app.include_router(sharing.router)
        app.include_router(mcp_auth.router)
        app.include_router(mcp_gateway.router)
        app.include_router(mcp_gateway_state.router)
        app.include_router(auth_info.router)
        app.include_router(auth_exchange.router)
        app.include_router(auth_identity.router)
        app.include_router(session.router)
        app.include_router(streaming.router)
        app.include_router(diagnostics.router)
        app.include_router(admin.router)
        app.include_router(signals.router)
        app.include_router(jobs.router)
        app.include_router(runs.router)
        app.include_router(schedules.router)
        app.include_router(chat_events.router)

        client = TestClient(app)
        # Lifespan runs on TestClient context enter.
        with client:
            # Optionally mount the events ingestion router.
            if (
                include_event_router
                and app_ctx.events is not None
                and getattr(app_ctx.events, "enabled", False)
                and getattr(app_ctx.events, "http_producer", None) is not None
            ):
                app.include_router(app_ctx.events.http_producer.router, tags=["events"])
            yield client
    finally:
        if client is not None:
            client.close()
        await app_ctx.release_resources()
        # Restore environment.
        os.environ.clear()
        os.environ.update(old_environ)
        # Best-effort temp cleanup.
        shutil.rmtree(tmp_root, ignore_errors=True)


@pytest.fixture
async def orchid_test_app(
    request: pytest.FixtureRequest,
    in_memory_vector_store: InMemoryVectorStore,
) -> AsyncIterator[TestClient]:
    """Fresh orchid-api TestClient for the example named by ``@pytest.mark.example``."""
    marker = request.node.get_closest_marker("example")
    example = marker.args[0] if marker else None
    async with build_orchid_test_app(
        example=example,
        vector_store=in_memory_vector_store,
    ) as client:
        yield client
