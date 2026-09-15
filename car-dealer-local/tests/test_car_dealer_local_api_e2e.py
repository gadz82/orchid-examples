"""API-level e2e scenarios for the car-dealer-local example.

These tests drive the car-dealer agent through orchid-api.  The agent
uses built-in content-source tools (list/search/read) against local
car specification files.
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


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("car-dealer-local")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="car-dealer-local",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("car-dealer-local")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="car-dealer-local",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("car-dealer-local")
async def test_car_dealer_uses_search_and_read_tools(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The car-dealer agent searches and reads local spec files."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about a car model",
        execution="sequential",
        agents=["car-dealer"],
    )
    factory.add_tool_calls(
        [
            {
                "name": "search_content_files",
                "args": {"query": "Camry"},
                "id": "tc-search",
            }
        ]
    )
    factory.add_tool_calls(
        [
            {
                "name": "read_content_file",
                "args": {"path": "camry-2025-specs.md"},
                "id": "tc-read",
            }
        ]
    )
    factory.add_text(
        "The 2025 Camry delivers 203 hp and up to 28 MPG city, "
        "with Toyota Safety Sense standard."
    )

    async with build_orchid_test_app(
        example="car-dealer-local",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Tell me about the Camry.")
        assert data["response"]
        assert "Camry" in data["response"]


@pytest.mark.example("car-dealer-local")
async def test_car_dealer_lists_available_models(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The car-dealer agent can list cars via the content source."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants to see available cars",
        execution="sequential",
        agents=["car-dealer"],
    )
    factory.add_tool_calls(
        [
            {
                "name": "list_content_files",
                "args": {"recursive": True},
                "id": "tc-list",
            }
        ]
    )
    factory.add_text(
        "Available models include the Camry, Accord, 3 Series, A4, F-150, and Golf."
    )

    async with build_orchid_test_app(
        example="car-dealer-local",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What cars do you have?")
        assert data["response"]
        assert "Camry" in data["response"]
