"""API-level e2e scenarios for the rag-strategies example.

These tests drive the retrieval-strategy showcase through orchid-api.
Each agent uses a different strategy against the same release-notes
knowledge base seeded by the startup hook.
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
    """Factory with one supervisor routing call + uniform text answers.

    Every text-consuming LLM call (reformulate, strategy internals,
    agent final) receives the same answer.  This keeps the test
    deterministic across strategies whose internal LLM call counts vary.
    """
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning=f"Route to {agent_name}",
        execution="sequential",
        agents=[agent_name],
    )
    # Provide enough uniform text responses to cover every strategy.
    for _ in range(6):
        factory.add_text(answer)
    return factory


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("rag-strategies")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="rag-strategies",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("rag-strategies")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="rag-strategies",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("rag-strategies")
async def test_simple_searcher_routes_and_answers(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The simple_searcher agent answers a release-history question."""
    factory = _make_factory(
        "simple_searcher",
        "Release 5.4 introduced SSE lifecycle markers.",
    )

    async with build_orchid_test_app(
        example="rag-strategies",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What changed in release 5.4?")
        assert data["response"]
        assert "5.4" in data["response"]


@pytest.mark.example("rag-strategies")
async def test_multi_query_searcher_routes_and_answers(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The multi_query_searcher agent answers a release-history question."""
    factory = _make_factory(
        "multi_query_searcher",
        "Release 5.2 shipped Phase A parallel tool dispatch.",
    )

    async with build_orchid_test_app(
        example="rag-strategies",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Tell me about parallel tool dispatch.")
        assert data["response"]
        assert "5.2" in data["response"]


@pytest.mark.example("rag-strategies")
async def test_hyde_searcher_routes_and_answers(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The hyde_searcher agent answers a release-history question."""
    factory = _make_factory(
        "hyde_searcher",
        "Release 5.0 added hierarchical RAG scopes.",
    )

    async with build_orchid_test_app(
        example="rag-strategies",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "When did hierarchical scopes arrive?")
        assert data["response"]
        assert "5.0" in data["response"]


@pytest.mark.example("rag-strategies")
async def test_recency_searcher_routes_and_answers(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The recency_searcher agent answers a release-history question."""
    factory = _make_factory(
        "recency_searcher",
        "The most recent release is 5.4 from April 2026.",
    )

    async with build_orchid_test_app(
        example="rag-strategies",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What is the latest release?")
        assert data["response"]
        assert "5.4" in data["response"]
