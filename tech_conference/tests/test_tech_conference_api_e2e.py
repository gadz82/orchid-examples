"""API-level e2e scenarios for the tech_conference example."""

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


@pytest.mark.example("tech_conference")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="tech_conference",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("tech_conference")
async def test_startup_hook_seeds_knowledge(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The startup hook populates the in-memory vector store."""
    async with build_orchid_test_app(
        example="tech_conference",
        vector_store=in_memory_vector_store,
    ):
        # The in-memory store should have documents in multiple namespaces.
        assert any(in_memory_vector_store.docs.get(ns) for ns in ["venue", "schedule", "visitor-services", "speaker-services"])


@pytest.mark.example("tech_conference")
async def test_venue_navigator_agent(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A venue question is routed to venue-navigator and answered."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about a room location",
        execution="sequential",
        agents=["venue-navigator"],
    )
    factory.add_text(
        "The AI/ML track is in Room 301 on the 3rd floor, Zone A. "
        "Take the elevator from registration and turn left."
    )

    async with build_orchid_test_app(
        example="tech_conference",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Where is the AI/ML track room?")
        assert data["response"]
        assert "Room 301" in data["response"]


@pytest.mark.example("tech_conference")
async def test_schedule_content_agent(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A schedule question is routed to schedule-content and answered."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about a keynote",
        execution="sequential",
        agents=["schedule-content"],
    )
    factory.add_text(
        "Dr. Sarah Chen's keynote 'The Future of AI' is on Day 1 at 9:00 AM in the Main Hall."
    )

    async with build_orchid_test_app(
        example="tech_conference",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "When is Dr. Sarah Chen's keynote?")
        assert data["response"]
        assert "Sarah Chen" in data["response"]


@pytest.mark.example("tech_conference")
async def test_cross_agent_skill_directions_and_sessions(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The orchestrator skill combines schedule + venue information."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about attending a session including location",
        execution="sequential",
        agents=["schedule-content"],  # first step of skill
    )
    factory.add_text(
        "Session details: 'Scaling LLMs' is on Day 2 at 2:00 PM in Room 204."
    )
    factory.add_text(
        "Room 204 is on the 2nd floor, Zone B. Take the stairs near registration."
    )
    factory.add_text(
        "You can attend 'Scaling LLMs' on Day 2 at 2:00 PM in Room 204 (2nd floor, Zone B)."
    )

    async with build_orchid_test_app(
        example="tech_conference",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(
            client,
            chat_id,
            "I want to attend the Scaling LLMs session. Where and when is it?",
        )
        assert data["response"]
        assert "Room 204" in data["response"]
