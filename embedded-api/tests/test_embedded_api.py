"""Tests mounting orchid-api routers into an existing FastAPI app."""

from __future__ import annotations

import importlib.util
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from examples._e2e_shared.fixtures.auth import DEFAULT_TOKEN
from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory


_EXAMPLE_DIR = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def _embedded_api_client() -> AsyncIterator[TestClient]:
    """Build a TestClient for ``my_existing_app`` with test doubles injected."""
    tmp_root = Path(tempfile.mkdtemp(prefix="orchid-embedded-api-e2e-"))

    old_environ = dict(os.environ)
    env_overrides: dict[str, str] = {
        "ORCHID_CONFIG": str(_EXAMPLE_DIR / "orchid.yml"),
        "AGENTS_CONFIG_PATH": str(_EXAMPLE_DIR / "agents.yaml"),
        "DEV_AUTH_BYPASS": "true",
        "DEV_BYPASS_TOKEN": DEFAULT_TOKEN,
        "CHAT_DB_DSN": str(tmp_root / "chats.db"),
        "MCP_TOKEN_STORE_DSN": str(tmp_root / "chats.db"),
        "MCP_CLIENT_REGISTRATION_STORE_DSN": str(tmp_root / "chats.db"),
        "MCP_GATEWAY_STATE_STORE_DSN": str(tmp_root / "chats.db"),
        "CHECKPOINTER_TYPE": "sqlite",
        "CHECKPOINTER_DSN": str(tmp_root / "checkpoints.db"),
        "VECTOR_BACKEND": "null",
        "CHAT_STORAGE_CLASS": "orchid_ai.persistence.sqlite.OrchidSQLiteChatStorage",
        "LANGSMITH_TRACING": "false",
        "ORCHID_ENABLE_PERF_LOGS": "false",
        "RATE_LIMIT_MESSAGES_PER_MINUTE": "0",
        "RATE_LIMIT_UPLOADS_PER_MINUTE": "0",
        "RATE_LIMIT_INDEX_PER_MINUTE": "0",
    }

    fake_factory = FakeChatModelFactory()
    fake_factory.add_structured_response(
        reasoning="Answer directly",
        execution="parallel",
        direct_response="I can help with that.",
    )
    fake_model = fake_factory.build()

    original_from_config_path: Any = None
    original_build_chat_model: Any = None

    try:
        os.environ.update(env_overrides)

        # Patch Orchid construction so the embedded app uses fakes.
        from orchid_ai.orchid.orchid import Orchid

        original_from_config_path = Orchid.from_config_path

        @classmethod
        async def _patched_from_config_path(cls, *args: Any, **kwargs: Any) -> Orchid:
            runtime_overrides = kwargs.get("runtime_overrides") or {}
            runtime_overrides["chat_model"] = fake_model
            kwargs["runtime_overrides"] = runtime_overrides
            return await original_from_config_path(*args, **kwargs)

        Orchid.from_config_path = _patched_from_config_path

        import orchid_ai.llm_factory as _llm_factory

        original_build_chat_model = _llm_factory.build_chat_model

        def _patched_build_chat_model(model_name: str, **kwargs: Any) -> Any:
            return fake_model

        _llm_factory.build_chat_model = _patched_build_chat_model

        # Import the example app only after env + patches are in place.
        # The directory name contains a hyphen so we load the module by file
        # location rather than by dotted package path.
        app_path = _EXAMPLE_DIR / "my_existing_app.py"
        spec = importlib.util.spec_from_file_location(
            "embedded_api_my_existing_app", str(app_path)
        )
        my_existing_app = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(my_existing_app)  # type: ignore[union-attr]

        with TestClient(my_existing_app.app) as client:
            yield client
    finally:
        if original_from_config_path is not None:
            Orchid.from_config_path = original_from_config_path
        if original_build_chat_model is not None:
            _llm_factory.build_chat_model = original_build_chat_model
        os.environ.clear()
        os.environ.update(old_environ)


@pytest.fixture
async def embedded_api_client() -> AsyncIterator[TestClient]:
    async with _embedded_api_client() as client:
        yield client


async def test_existing_app_health_and_products(embedded_api_client: TestClient) -> None:
    """The integrator's own routes remain available alongside orchid's."""
    health = embedded_api_client.get("/healthz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    products = embedded_api_client.get("/products")
    assert products.status_code == 200
    data = products.json()
    assert len(data) == 3
    assert data[0]["sku"] == "SKU-001"

    single = embedded_api_client.get("/products/SKU-001")
    assert single.status_code == 200
    assert single.json()["sku"] == "SKU-001"


async def test_orchid_routes_create_and_send_message(embedded_api_client: TestClient) -> None:
    """Orchid routers mounted under ``/ai`` can create chats and send messages."""
    headers = {"Authorization": f"Bearer {DEFAULT_TOKEN}"}

    create_resp = embedded_api_client.post("/ai/chats", json={"title": "embedded test"}, headers=headers)
    assert create_resp.status_code == 200
    chat_id = create_resp.json()["id"]

    list_resp = embedded_api_client.get("/ai/chats", headers=headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == chat_id for c in list_resp.json())

    send_resp = embedded_api_client.post(
        f"/ai/chats/{chat_id}/messages",
        data={"message": "Hello from the embedded app"},
        headers=headers,
    )
    assert send_resp.status_code == 200
    body = send_resp.json()
    assert body["response"]
    assert body["chat_id"] == chat_id


async def test_orchid_stream_endpoint(embedded_api_client: TestClient) -> None:
    """The streaming endpoint under ``/ai`` returns SSE chunks."""
    headers = {"Authorization": f"Bearer {DEFAULT_TOKEN}"}

    create_resp = embedded_api_client.post("/ai/chats", json={"title": "stream test"}, headers=headers)
    assert create_resp.status_code == 200
    chat_id = create_resp.json()["id"]

    with embedded_api_client.stream(
        "POST",
        f"/ai/chats/{chat_id}/messages/stream",
        data={"message": "Stream me"},
        headers=headers,
    ) as stream_resp:
        assert stream_resp.status_code == 200
        chunks = [chunk for chunk in stream_resp.iter_text() if chunk]

    assert chunks
