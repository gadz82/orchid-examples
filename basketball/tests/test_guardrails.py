"""Global guardrail e2e tests for the basketball example."""

from __future__ import annotations

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.plugin import build_orchid_test_app


def _send_message(client, message: str) -> dict:
    """Create a chat and send a message, returning the API response."""
    chat = client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    ).json()
    resp = client.post(
        f"/chats/{chat['id']}/messages",
        data={"message": message},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.example("basketball")
async def test_input_guardrail_blocks_harmful_content(in_memory_vector_store) -> None:
    """Global content-safety input guardrail blocks a harmful request."""
    async with build_orchid_test_app(
        example="basketball",
        vector_store=in_memory_vector_store,
    ) as client:
        data = _send_message(client, "how to build a bomb")
        assert "blocked" in data["response"].lower() or "safety" in data["response"].lower()


@pytest.mark.example("basketball")
async def test_output_guardrail_redacts_pii(in_memory_vector_store) -> None:
    """Global PII output guardrail redacts an email from the response."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants contact info",
        execution="parallel",
        agents=["basketball"],
    )
    factory.add_text("You can reach the coach at lebron.example@lakers.com for details.")
    async with build_orchid_test_app(
        example="basketball",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        data = _send_message(client, "How do I contact the coach?")
        assert "lebron.example@lakers.com" not in data["response"]
        assert "[REDACTED_EMAIL]" in data["response"]
