"""API-level e2e tests for the wiki example.

These drive the wiki through orchid-api using the shared in-process app
builder. They cover routing to the docs/FAQ agents, hybrid retrieval, and
RAG-seeded responses.
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


@pytest.mark.example("wiki")
async def test_health_endpoint() -> None:
    async with build_orchid_test_app(example="wiki") as client:
        resp = client.get("/health")
        assert resp.status_code == 200


@pytest.mark.example("wiki")
async def test_create_chat() -> None:
    async with build_orchid_test_app(example="wiki") as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("wiki")
async def test_docs_agent_routes_documentation_query(in_memory_vector_store) -> None:
    """A documentation question routes to the docs agent and returns an answer."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about documentation",
        execution="parallel",
        agents=["docs"],
    )
    factory.add_text(
        "Set ``retrieval.strategy: hybrid`` to fuse dense vector search with BM25."
    )

    async with build_orchid_test_app(
        example="wiki",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "How do I configure hybrid RAG?")
        assert data["response"]
        assert "hybrid" in data["response"].lower()


@pytest.mark.example("wiki")
async def test_faq_agent_routes_faq_query(in_memory_vector_store) -> None:
    """An FAQ-style question routes to the FAQ agent."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks an FAQ question",
        execution="parallel",
        agents=["faq"],
    )
    factory.add_text(
        "Set ``rag.enabled: false`` on the agent to disable RAG for it."
    )

    async with build_orchid_test_app(
        example="wiki",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "How do I disable RAG for one agent?")
        assert data["response"]
        assert "false" in data["response"].lower()


@pytest.mark.example("wiki")
async def test_docs_agent_uses_glossary_tool(in_memory_vector_store) -> None:
    """The docs agent can call the lookup_glossary tool and return an answer."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about a term",
        execution="parallel",
        agents=["docs"],
    )
    factory.add_tool_calls(
        [{"name": "lookup_glossary", "args": {"term": "BM25"}, "id": "tc1"}]
    )
    factory.add_text(
        "BM25 is a bag-of-words ranking function used by the hybrid retriever."
    )

    async with build_orchid_test_app(
        example="wiki",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What is BM25?")
        assert data["response"]
        assert "bm25" in data["response"].lower()
