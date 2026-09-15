"""Live-server e2e tests for the weather example.

These tests assume the weather Docker stack is running (including the
weather-mcp service and PostgreSQL). When ``ORCHID_API_URL`` is not set
they are skipped automatically.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ORCHID_API_URL", "") == "",
    reason="Live weather API URL not configured (set ORCHID_API_URL)",
)


async def test_health(api_client) -> None:
    """The deployed API reports healthy."""
    resp = await api_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"


async def test_create_chat_persists(api_client) -> None:
    """A chat created via the live API is listable."""
    resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data

    list_resp = await api_client.get(
        "/chats",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert list_resp.status_code == 200
    chats = list_resp.json()
    assert any(c["id"] == data["id"] for c in chats)


async def test_send_message_returns_response(api_client) -> None:
    """Sending a weather question returns a response."""
    chat_resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    chat_id = chat_resp.json()["id"]

    resp = await api_client.post(
        f"/chats/{chat_id}/messages",
        data={"message": "What should I wear in London today?"},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"]


async def test_message_history_is_persisted(api_client) -> None:
    """Exchanged messages are retrievable from chat history."""
    chat_resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    chat_id = chat_resp.json()["id"]

    await api_client.post(
        f"/chats/{chat_id}/messages",
        data={"message": "Will it rain tomorrow?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    history_resp = await api_client.get(
        f"/chats/{chat_id}/messages",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert history_resp.status_code == 200
    messages = history_resp.json()
    roles = {m["role"] for m in messages}
    assert "user" in roles
    assert "assistant" in roles
