"""Chat persistence e2e test for the basketball example."""

from __future__ import annotations

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.plugin import build_orchid_test_app


def _create_chat(client) -> str:
    """Create a chat and return its id."""
    resp = client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _send_message(client, chat_id: str, message: str) -> dict:
    """Send a message to an existing chat, returning the API response."""
    resp = client.post(
        f"/chats/{chat_id}/messages",
        data={"message": message},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.example("basketball")
async def test_multi_turn_persists_messages(in_memory_vector_store) -> None:
    """User and assistant messages are persisted and returned by the history endpoint."""
    factory = FakeChatModelFactory()
    # Queue plenty of deterministic responses for two turns.
    for _ in range(2):
        factory.add_structured_response(
            reasoning="Route to basketball agent",
            execution="parallel",
            agents=["basketball"],
        )
        factory.add_text("LeBron James plays for the Los Angeles Lakers.")

    async with build_orchid_test_app(
        example="basketball",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data1 = _send_message(client, chat_id, "Tell me about LeBron")
        assert data1["response"]

        history_resp = client.get(
            f"/chats/{chat_id}/messages",
            headers={"Authorization": "Bearer dev-token"},
        )
        assert history_resp.status_code == 200
        messages = history_resp.json()
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert "LeBron" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"]

        data2 = _send_message(client, chat_id, "Which team does he play for?")
        assert data2["response"]

        history_resp2 = client.get(
            f"/chats/{chat_id}/messages",
            headers={"Authorization": "Bearer dev-token"},
        )
        messages2 = history_resp2.json()
        assert len(messages2) == 4
        assert messages2[-2]["role"] == "user"
        assert "team" in messages2[-2]["content"].lower()
        assert messages2[-1]["role"] == "assistant"
        assert messages2[-1]["content"]
