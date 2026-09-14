"""API-level e2e scenarios for the architecture_review example.

These tests drive the three-agent design-review board through orchid-api.
Each specialist agent (structural, cost, sustainability) is exercised with
one of its built-in tools.
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


@pytest.mark.example("architecture_review")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="architecture_review",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("architecture_review")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="architecture_review",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("architecture_review")
async def test_structural_agent_runs_analysis_tool(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The structural agent calls analyze_structure and returns an answer."""
    factory = _make_factory(
        "structural",
        "analyze_structure",
        {"building_type": "office", "floors": 5, "area_m2": 2000},
        "For a 5-storey office building, a steel frame with CLT slabs is recommended.",
    )

    async with build_orchid_test_app(
        example="architecture_review",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Analyze this office building.")
        assert data["response"]
        assert "steel" in data["response"].lower() or "CLT" in data["response"]


@pytest.mark.example("architecture_review")
async def test_cost_agent_runs_cost_tool(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The cost agent calls estimate_construction_cost and returns an answer."""
    factory = _make_factory(
        "cost",
        "estimate_construction_cost",
        {"building_type": "office", "area_m2": 2000, "quality_tier": "standard"},
        "The estimated construction cost is approximately $2,400 per m².",
    )

    async with build_orchid_test_app(
        example="architecture_review",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What is the construction budget?")
        assert data["response"]
        assert "$" in data["response"] or "cost" in data["response"].lower()


@pytest.mark.example("architecture_review")
async def test_sustainability_agent_runs_certification_tool(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The sustainability agent calls evaluate_certification and returns an answer."""
    factory = _make_factory(
        "sustainability",
        "evaluate_certification",
        {"certification": "LEED", "building_type": "office"},
        "LEED certification is achievable for this office with 60-70 points.",
    )

    async with build_orchid_test_app(
        example="architecture_review",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Can we get LEED certification?")
        assert data["response"]
        assert "LEED" in data["response"]
