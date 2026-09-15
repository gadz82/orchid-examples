"""API-level e2e scenarios for the custom-storage example.

These tests drive the echo agent through orchid-api and verify that the
custom JSON-file storage backend persists chats and messages.
"""

from __future__ import annotations

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.fixtures.mock_vector import InMemoryVectorStore
from examples._e2e_shared.plugin import build_orchid_test_app

# ── helpers ────────────────────────────────────────────────────


def _create_chat(client) -> str:
    resp = client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _send_message(client, chat_id: str, message: str) -> dict:
    resp = client.post(
        f"/chats/{chat_id}/messages",
        data={"message": message},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("custom-storage")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="custom-storage",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("custom-storage")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API using the custom storage backend."""
    async with build_orchid_test_app(
        example="custom-storage",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id

        # Verify the chat is persisted and listable.
        resp = client.get("/chats", headers={"Authorization": "Bearer dev-token"})
        assert resp.status_code == 200
        chats = resp.json()
        assert any(c["id"] == chat_id for c in chats)


@pytest.mark.example("custom-storage")
async def test_echo_agent_responds_and_message_is_persisted(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The echo agent returns an answer and the message is stored."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User sends a greeting",
        execution="sequential",
        agents=["echo"],
    )
    factory.add_text("Hello! Your message is being persisted to a JSON file.")

    async with build_orchid_test_app(
        example="custom-storage",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Hi there!")
        assert data["response"]
        assert "persisted" in data["response"].lower() or "JSON" in data["response"]

        # Verify the message is retrievable from history.
        resp = client.get(
            f"/chats/{chat_id}/messages",
            headers={"Authorization": "Bearer dev-token"},
        )
        assert resp.status_code == 200
        messages = resp.json()
        assert any("Hi there!" in m.get("content", "") for m in messages)

