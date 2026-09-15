"""Live-server e2e tests for the postgres-storage example.

These tests assume the postgres-storage Docker stack is running
(``script/start_postgres_storage.sh`` or the example's own
``docker-compose.yml``). When ``ORCHID_API_URL`` is not reachable they
are skipped automatically.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("ORCHID_API_URL", "") == "",
    reason="Live postgres-storage API URL not configured (set ORCHID_API_URL)",
)


async def test_health(api_client) -> None:
    resp = await api_client.get("/health")
    assert resp.status_code == 200


async def test_create_chat_persists_to_postgres(api_client) -> None:
    resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data

    # Chat should be listable (proves PostgreSQL storage round-trip).
    list_resp = await api_client.get(
        "/chats",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert list_resp.status_code == 200
    chats = list_resp.json()
    assert any(c["id"] == data["id"] for c in chats)


async def test_send_message_returns_response(api_client) -> None:
    chat_resp = await api_client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    chat_id = chat_resp.json()["id"]

    resp = await api_client.post(
        f"/chats/{chat_id}/messages",
        data={"message": "Hello from postgres storage"},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"]

    # Message should be persisted.
    history_resp = await api_client.get(
        f"/chats/{chat_id}/messages",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert history_resp.status_code == 200
    messages = history_resp.json()
    roles = {m["role"] for m in messages}
    assert "user" in roles
    assert "assistant" in roles
