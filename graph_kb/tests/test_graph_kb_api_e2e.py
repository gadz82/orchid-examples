"""API-level e2e scenarios for the graph_kb example.

These tests drive the GraphRAG demo through orchid-api using the shared
in-process app builder.  They cover health, chat creation, and org-chart
query routing through the ``org_chart`` agent.
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


def _make_factory(agent_response: str) -> FakeChatModelFactory:
    """Factory with one supervisor routing call + one agent answer."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about the org chart",
        execution="sequential",
        agents=["org_chart"],
    )
    factory.add_text(agent_response)
    return factory


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("graph_kb")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="graph_kb",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("graph_kb")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="graph_kb",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("graph_kb")
async def test_org_chart_agent_answers_reporting_query(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A "who reports to" question routes to the org_chart agent."""
    factory = _make_factory("Bob and Carol report to Alice.")

    async with build_orchid_test_app(
        example="graph_kb",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Who reports to Alice?")
        assert data["response"]
        assert "report" in data["response"].lower()


@pytest.mark.example("graph_kb")
async def test_org_chart_agent_answers_project_query(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A "who works on" question routes to the org_chart agent."""
    factory = _make_factory("Bob and Dave work on the Atlas project.")

    async with build_orchid_test_app(
        example="graph_kb",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Who works on Atlas?")
        assert data["response"]
        assert "Atlas" in data["response"]


@pytest.mark.example("graph_kb")
async def test_org_chart_agent_handles_two_hop_relation(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A two-hop org-chart question routes to the org_chart agent."""
    factory = _make_factory("Dave reports to Bob, who reports to Alice.")

    async with build_orchid_test_app(
        example="graph_kb",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Who does Dave's manager report to?")
        assert data["response"]
        assert "Alice" in data["response"]
