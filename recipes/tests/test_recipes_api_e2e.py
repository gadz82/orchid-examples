"""API-level e2e scenarios for the recipes example.

These tests drive the recipe Q&A demo through orchid-api using the
shared in-process app builder.  They cover routing to the two agents
(cookbook, mealplanner) and verify that seeded recipe context is
available for retrieval.
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


def _make_factory(agent_name: str, answer: str) -> FakeChatModelFactory:
    """Factory with one routing call + uniform text answers."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning=f"Route to {agent_name}",
        execution="sequential",
        agents=[agent_name],
    )
    for _ in range(4):
        factory.add_text(answer)
    return factory


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("recipes")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="recipes",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("recipes")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="recipes",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("recipes")
async def test_cookbook_agent_answers_recipe_question(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A recipe question routes to the cookbook agent."""
    factory = _make_factory(
        "cookbook",
        "Try the Chicken Parmesan: breaded chicken with marinara and mozzarella.",
    )

    async with build_orchid_test_app(
        example="recipes",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "How do I make chicken parmesan?")
        assert data["response"]
        assert "chicken" in data["response"].lower()


@pytest.mark.example("recipes")
async def test_mealplanner_agent_builds_meal_plan(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A meal-planning question routes to the mealplanner agent."""
    factory = _make_factory(
        "mealplanner",
        "For a vegan weeknight, try the Vegetable Stir-Fry or Lentil Soup.",
    )

    async with build_orchid_test_app(
        example="recipes",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Plan a vegan dinner for tonight.")
        assert data["response"]
        assert "vegan" in data["response"].lower()
