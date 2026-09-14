"""Live-server e2e tests for the fm_agent example.

These tests assume the fm_agent Docker stack is running. When
``ORCHID_API_URL`` is not set they are skipped automatically.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ORCHID_API_URL", "") == "",
    reason="Live fm_agent API URL not configured (set ORCHID_API_URL)",
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
    """Sending a message to the live API returns a response."""
    chat_resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    chat_id = chat_resp.json()["id"]

    resp = await api_client.post(
        f"/chats/{chat_id}/messages",
        data={"message": "What is the notification service responsible for?"},
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
        data={"message": "Hello fm-agent"},
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


async def test_delete_chat(api_client) -> None:
    """A chat can be deleted via the live API."""
    chat_resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    chat_id = chat_resp.json()["id"]

    del_resp = await api_client.delete(
        f"/chats/{chat_id}",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert del_resp.status_code == 200

    list_resp = await api_client.get(
        "/chats",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert list_resp.status_code == 200
    chats = list_resp.json()
    assert not any(c["id"] == chat_id for c in chats)
