"""API-level e2e scenarios for the md-config example.

These tests drive the Markdown-configured basketball/psychologist demo
through orchid-api.  They verify that config loading works from
``orchid.md`` + ``agents/*.md`` files.
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


@pytest.mark.example("md-config")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="md-config",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("md-config")
async def test_create_chat(in_memory_vector_store: InMemoryVectorStore) -> None:
    """A chat can be created through the API."""
    async with build_orchid_test_app(
        example="md-config",
        vector_store=in_memory_vector_store,
    ) as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("md-config")
async def test_basketball_agent_routes_from_md_config(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A basketball question routes to the basketball agent configured in Markdown."""
    factory = _make_factory(
        "basketball",
        "get_player_stats",
        {"player_name": "LeBron James"},
        "LeBron James averages 27.2 PPG, 7.5 RPG, and 7.3 APG.",
    )

    async with build_orchid_test_app(
        example="md-config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "How is LeBron performing?")
        assert data["response"]
        assert "LeBron" in data["response"]


@pytest.mark.example("md-config")
async def test_psychologist_agent_routes_from_md_config(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A psychology question routes to the psychologist agent configured in Markdown."""
    factory = _make_factory(
        "psychologist",
        "assess_motivation",
        {"player_name": "LeBron James"},
        "LeBron shows high intrinsic motivation with strong leadership resilience.",
    )

    async with build_orchid_test_app(
        example="md-config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Assess LeBron's motivation.")
        assert data["response"]
        assert "motivation" in data["response"].lower()
