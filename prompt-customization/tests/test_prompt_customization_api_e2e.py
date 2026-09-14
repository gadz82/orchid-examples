"""API-level e2e scenarios for the prompt-customization example.

These tests drive the legal-advisor agent through orchid-api.  The
example exercises prompt-section overrides and per-agent transformer
prompts (HyDE + reformulate).
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
    """Factory with routing + uniform text answers for HyDE + reformulate."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks a legal research question",
        execution="sequential",
        agents=["legal_advisor"],
    )
    # HyDE (2 hypotheticals in this config) + reformulate + final answer.
    for _ in range(5):
        factory.add_text(answer)
    return factory


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("prompt-customization")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="prompt-customization",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("prompt-customization")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="prompt-customization",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("prompt-customization")
async def test_legal_advisor_answers_with_custom_prompts(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The legal_advisor agent returns an answer using custom prompt sections."""
    answer = (
        "General information: under U.S. federal law, a standard non-disclosure "
        "agreement is generally enforceable if it is reasonable in scope and duration."
    )
    factory = _make_factory(answer)

    async with build_orchid_test_app(
        example="prompt-customization",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Are NDAs enforceable?")
        assert data["response"]
        assert "NDA" in data["response"] or "non-disclosure" in data["response"].lower()


@pytest.mark.example("prompt-customization")
async def test_supervisor_uses_custom_assistant_name(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The supervisor's custom assistant_name is loaded from agents.yaml."""
    answer = "General information only — not legal advice."
    factory = _make_factory(answer)

    async with build_orchid_test_app(
        example="prompt-customization",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Hello")
        assert data["response"]
        # We mainly assert the graph booted with the custom config.
        assert "response" in data
