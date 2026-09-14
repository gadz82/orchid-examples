"""API-level e2e scenarios for the gallery_curator example.

These tests drive the gallery-curator demo through orchid-api.  The
example exercises the conversation-memory pipeline (running summaries,
structured output, RAG memory), so the fake model provides uniform
responses to keep the tests deterministic.
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


def _make_factory(answer: str) -> FakeChatModelFactory:
    """Factory with routing + enough uniform text answers for memory."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="Route to gallery-curator",
        execution="sequential",
        agents=["gallery-curator"],
    )
    for _ in range(8):
        factory.add_text(answer)
    return factory


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("gallery_curator")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="gallery_curator",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("gallery_curator")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="gallery_curator",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("gallery_curator")
async def test_curator_answers_art_question(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The gallery-curator agent answers a single-turn art question."""
    answer = "Yayoi Kusama is known for infinity mirror rooms and polka dots."
    factory = _make_factory(answer)

    async with build_orchid_test_app(
        example="gallery_curator",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Tell me about Yayoi Kusama.")
        assert data["response"]
        assert "Kusama" in data["response"]


@pytest.mark.example("gallery_curator")
async def test_curator_maintains_context_across_turns(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The gallery-curator agent keeps answering across multiple turns."""
    answer = "Gerhard Richter is a German painter working across photorealism and abstraction."
    factory = _make_factory(answer)

    async with build_orchid_test_app(
        example="gallery_curator",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        first = _send_message(client, chat_id, "Who is Gerhard Richter?")
        assert "Richter" in first["response"]

        second = _send_message(client, chat_id, "What is his main medium?")
        assert "Richter" in second["response"]
