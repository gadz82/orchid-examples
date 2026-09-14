"""API-level e2e scenarios for the festival_producer example.

These tests drive the three-agent festival-planning board through orchid-api.
Each specialist agent (artist-booking, logistics, marketing) is exercised
with one of its built-in tools.
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


def _make_factory(agent_name: str, tool_name: str, tool_args: dict, answer: str) -> FakeChatModelFactory:
    """Factory with routing + one tool call + final answer."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning=f"Route to {agent_name}",
        execution="sequential",
        agents=[agent_name],
    )
    factory.add_tool_calls(
        [
            {
                "name": tool_name,
                "args": tool_args,
                "id": "tc1",
            }
        ]
    )
    factory.add_text(answer)
    return factory


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("festival_producer")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="festival_producer",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("festival_producer")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="festival_producer",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("festival_producer")
async def test_artist_booking_agent_looks_up_artist(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The artist-booking agent calls lookup_artist and returns an answer."""
    factory = _make_factory(
        "artist-booking",
        "lookup_artist",
        {"artist_name": "Neon Pulse"},
        "Neon Pulse is an electronic act available in Q3 for $45K.",
    )

    async with build_orchid_test_app(
        example="festival_producer",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Tell me about Neon Pulse.")
        assert data["response"]
        assert "Neon Pulse" in data["response"]


@pytest.mark.example("festival_producer")
async def test_logistics_agent_checks_venue(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The logistics agent calls check_venue_availability and returns an answer."""
    factory = _make_factory(
        "logistics",
        "check_venue_availability",
        {"stage_name": "Main Stage"},
        "Main Stage has a 20kW power grid and is available on Saturday.",
    )

    async with build_orchid_test_app(
        example="festival_producer",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Is the Main Stage available?")
        assert data["response"]
        assert "Main Stage" in data["response"]


@pytest.mark.example("festival_producer")
async def test_marketing_agent_analyzes_demographics(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The marketing agent calls analyze_demographics and returns an answer."""
    factory = _make_factory(
        "marketing",
        "analyze_demographics",
        {"genre": "indie rock"},
        "Indie rock fans skew 25-34, urban, high streaming engagement.",
    )

    async with build_orchid_test_app(
        example="festival_producer",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Who listens to indie rock?")
        assert data["response"]
        assert "indie rock" in data["response"].lower()
