"""API-level e2e scenarios for the hospital_front_office example."""

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


@pytest.mark.example("hospital_front_office")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="hospital_front_office",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("hospital_front_office")
async def test_startup_hook_seeds_knowledge(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The startup hook populates the in-memory vector store."""
    async with build_orchid_test_app(
        example="hospital_front_office",
        vector_store=in_memory_vector_store,
    ):
        assert any(
            in_memory_vector_store.docs.get(ns)
            for ns in ["departments", "bureaucracy", "opening-hours", "emergency"]
        )


@pytest.mark.example("hospital_front_office")
async def test_department_navigator_agent(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A wayfinding question is routed to department-navigator."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks for cardiology department location",
        execution="sequential",
        agents=["department-navigator"],
    )
    factory.add_text(
        "Cardiology is on the 2nd floor, East Wing. Take elevator B from the main entrance."
    )

    async with build_orchid_test_app(
        example="hospital_front_office",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Where is cardiology?")
        assert data["response"]
        assert "2nd floor" in data["response"]


@pytest.mark.example("hospital_front_office")
async def test_bureaucracy_procedures_agent(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A paperwork question is routed to bureaucracy-procedures."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks how to register as a new patient",
        execution="sequential",
        agents=["bureaucracy-procedures"],
    )
    factory.add_text(
        "Bring a photo ID, insurance card, and referral to the Admissions Office on the ground floor."
    )

    async with build_orchid_test_app(
        example="hospital_front_office",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "How do I register as a new patient?")
        assert data["response"]
        assert "Admissions Office" in data["response"]


@pytest.mark.example("hospital_front_office")
async def test_cross_agent_skill_indications_and_hours(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The cross-agent skill combines department location with opening hours."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about visiting radiology including when",
        execution="sequential",
        agents=["department-navigator"],
    )
    factory.add_text("Radiology is on the 1st floor, West Wing, near the pharmacy.")
    factory.add_text("Radiology is open Monday-Friday 8:00 AM - 6:00 PM; booking is required.")
    factory.add_text(
        "Radiology is on the 1st floor, West Wing, and is open Monday-Friday 8:00 AM - 6:00 PM."
    )

    async with build_orchid_test_app(
        example="hospital_front_office",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(
            client,
            chat_id,
            "I need a radiology scan. Where is it and when is it open?",
        )
        assert data["response"]
        assert "1st floor" in data["response"]
