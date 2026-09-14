"""API-level e2e scenarios for the orchid_experts example."""

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


@pytest.mark.example("orchid_experts")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="orchid_experts",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("orchid_experts")
async def test_startup_hook_seeds_knowledge(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The startup hook populates the in-memory vector store."""
    async with build_orchid_test_app(
        example="orchid_experts",
        vector_store=in_memory_vector_store,
    ):
        namespaces = [
            "orchid-framework",
            "rag-system",
            "tools-skills",
            "mcp-system",
            "auth-system",
            "bloom-events",
            "orchid-api-pkg",
            "orchid-cli-pkg",
            "orchid-frontend-pkg",
            "ai-integration",
        ]
        assert any(in_memory_vector_store.docs.get(ns) for ns in namespaces)


@pytest.mark.example("orchid_experts")
async def test_orchid_framework_expert(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A framework question routes to the orchid expert."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about GenericAgent pipeline",
        execution="sequential",
        agents=["orchid"],
    )
    factory.add_text(
        "The GenericAgent pipeline has six steps: RAG, skill check, MCP tools, built-in tools, dynamic RAG injection, and final summarisation."
    )

    async with build_orchid_test_app(
        example="orchid_experts",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "How does the GenericAgent pipeline work?")
        assert data["response"]
        assert "six steps" in data["response"]


@pytest.mark.example("orchid_experts")
async def test_rag_system_expert(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A RAG question routes to the rag expert."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about RAG scope hierarchy",
        execution="sequential",
        agents=["rag"],
    )
    factory.add_text(
        "OrchidRAGScope has five levels: root, tenant, user, chat, and agent."
    )

    async with build_orchid_test_app(
        example="orchid_experts",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Explain the RAG scope hierarchy")
        assert data["response"]
        assert "five levels" in data["response"]


@pytest.mark.example("orchid_experts")
async def test_mcp_system_expert(in_memory_vector_store: InMemoryVectorStore) -> None:
    """An MCP question routes to the mcp expert."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about MCP auth modes",
        execution="sequential",
        agents=["mcp"],
    )
    factory.add_text(
        "MCP servers support three auth modes: none, passthrough, and oauth."
    )

    async with build_orchid_test_app(
        example="orchid_experts",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(
            client,
            chat_id,
            "What MCP auth modes are supported?",
        )
        assert data["response"]
        assert "auth modes" in data["response"]
