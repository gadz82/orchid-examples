"""API-level e2e smoke tests for the travel-agency example.

These drive the example through orchid-api using the shared in-process
app builder. They cover health, chat creation, and simple agent routing.
"""

from __future__ import annotations

import pytest
from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.plugin import build_orchid_test_app


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


@pytest.mark.example("travel-agency/config")
async def test_health_endpoint() -> None:
    async with build_orchid_test_app(example="travel-agency/config") as client:
        resp = client.get("/health")
        assert resp.status_code == 200


@pytest.mark.example("travel-agency/config")
async def test_create_chat() -> None:
    async with build_orchid_test_app(example="travel-agency/config") as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("travel-agency/config")
async def test_flights_agent_responds_to_search_query(in_memory_vector_store) -> None:
    """A flight search query routes to the flights agent and returns options."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants to search flights",
        execution="parallel",
        agents=["flights"],
    )
    factory.add_tool_calls(
        [
            {
                "name": "search_flights",
                "args": {"origin": "NYC", "destination": "LON"},
                "id": "tc1",
            }
        ]
    )
    factory.add_text("Flight BA112 from JFK to LHR departs 8:00 PM, $540.")

    async with build_orchid_test_app(
        example="travel-agency/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Find flights from NYC to London")
        assert data["response"]
        assert "flight" in data["response"].lower()


@pytest.mark.example("travel-agency/config")
async def test_hotels_agent_responds_to_search_query(in_memory_vector_store) -> None:
    """A hotel search query routes to the hotels agent and returns options."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants to search hotels",
        execution="parallel",
        agents=["hotels"],
    )
    factory.add_tool_calls(
        [
            {
                "name": "search_hotels",
                "args": {"city": "London"},
                "id": "tc1",
            }
        ]
    )
    factory.add_text("Hotel Covent Garden Inn, 4 stars, $180/night.")

    async with build_orchid_test_app(
        example="travel-agency/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Find hotels in London")
        assert data["response"]
        assert "hotel" in data["response"].lower()


@pytest.mark.example("travel-agency/config")
async def test_sequential_skill_routes_through_pipeline(in_memory_vector_store) -> None:
    """The plan_trip orchestrator skill chains flights → hotels → itinerary."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants a full trip plan",
        execution="skill",
        skill="plan_trip",
    )
    # Each agent step in the sequential pipeline needs a tool call + final text.
    for _ in range(3):
        factory.add_tool_calls([{"name": "search_flights", "args": {}, "id": f"tc-{_}"}])
        factory.add_text(f"Step {_ + 1} of the trip plan is ready.")

    async with build_orchid_test_app(
        example="travel-agency/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Plan a trip to London")
        assert data["response"]
        assert "trip" in data["response"].lower()
