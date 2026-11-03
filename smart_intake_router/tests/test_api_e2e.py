"""API-level e2e coverage for the smart intake router example.

Boots the real orchid-api app with the example's YAML, the real decision
provider factory (stub profile), and a deterministic chat model, then sends
requests through the HTTP surface.
"""

from __future__ import annotations

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModel
from examples._e2e_shared.plugin import build_orchid_test_app

HEADERS = {"Authorization": "Bearer dev-token"}


def _create_chat(client) -> str:
    response = client.post("/chats", json={}, headers=HEADERS)
    assert response.status_code == 200
    return response.json()["id"]


def _send_message(client, chat_id: str, message: str) -> dict:
    response = client.post(
        f"/chats/{chat_id}/messages",
        data={"message": message},
        headers=HEADERS,
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.example("smart_intake_router")
async def test_example_boots_and_routes_through_the_api(in_memory_vector_store) -> None:
    chat_model = FakeChatModel(
        [
            {
                "content": (
                    "INV-1042 was charged twice on 2026-10-14. "
                    "The duplicate charge is eligible for a refund."
                )
            }
        ]
    )
    async with build_orchid_test_app(
        example="smart_intake_router/config",
        vector_store=in_memory_vector_store,
        chat_model=chat_model,
    ) as client:
        assert client.get("/health").status_code == 200
        chat_id = _create_chat(client)
        result = _send_message(client, chat_id, "I was charged twice for the same invoice")
        assert isinstance(result.get("response"), str)
        assert result["response"]


@pytest.mark.example("smart_intake_router")
async def test_refund_request_boots_with_the_skill_profile(in_memory_vector_store) -> None:
    chat_model = FakeChatModel([{"content": "I checked the invoice; the refund path is ready."}])
    async with build_orchid_test_app(
        example="smart_intake_router/config",
        vector_store=in_memory_vector_store,
        chat_model=chat_model,
    ) as client:
        chat_id = _create_chat(client)
        result = _send_message(client, chat_id, "Please refund the duplicate charge")
        assert result.get("response")
