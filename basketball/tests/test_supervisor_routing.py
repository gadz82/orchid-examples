"""Supervisor routing e2e tests for the basketball example."""

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
async def test_send_message_receives_response(in_memory_vector_store) -> None:
    """A basic chat turn returns a non-empty assistant response."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants basketball stats",
        execution="parallel",
        agents=["basketball"],
    )
    factory.add_text("LeBron James averages 25.7 points per game for the Lakers.")
    async with build_orchid_test_app(
        example="basketball",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        data = _send_message(client, "Tell me about LeBron")
        assert data["response"]
        assert "LeBron" in data["response"]


@pytest.mark.example("basketball")
async def test_lebron_question_routes_to_basketball_agent(in_memory_vector_store) -> None:
    """A basketball player question is routed to the basketball agent."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asked about an NBA player",
        execution="parallel",
        agents=["basketball"],
    )
    factory.add_text(
        "LeBron James is a forward for the Los Angeles Lakers, averaging "
        "25.7 PPG, 7.3 RPG and 8.3 APG."
    )
    async with build_orchid_test_app(
        example="basketball",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        data = _send_message(client, "Tell me about LeBron")
        assert "Lakers" in data["response"]
        assert "25.7" in data["response"]


@pytest.mark.example("basketball")
async def test_stressed_question_routes_to_psychologist_agent(in_memory_vector_store) -> None:
    """A mental-performance question is routed to the psychologist agent."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User mentions stress and mental state",
        execution="parallel",
        agents=["psychologist"],
    )
    factory.add_text(
        "It's completely normal for athletes to feel stressed. Let's explore "
        "breathing techniques and mental reframing strategies."
    )
    async with build_orchid_test_app(
        example="basketball",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        data = _send_message(client, "I'm feeling stressed before the game")
        assert "stress" in data["response"].lower()
        assert "mental" in data["response"].lower()
