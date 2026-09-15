"""API-level e2e scenarios for the car_dealer_fleet example.

The fleet is normally generated dynamically by the startup hook using an
LLM over content sources.  For deterministic, offline e2e tests we seed
the SQLite config store with a small pre-baked fleet via
``ORCHID_FLEET_SEED_PATH``.
"""

from __future__ import annotations

import json

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


def _seed_fleet(tmp_path) -> str:
    """Write a small JSON fleet seed and return the file path."""
    seed = [
        {
            "name": "toyota-expert",
            "description": "Specialist in Toyota Camry specifications",
            "prompt": (
                "You are the Toyota vehicle expert.\n\n"
                "Key Specifications (Toyota Camry 2025):\n"
                "- Engine: 2.5L 4-cylinder, 203 hp\n"
                "- Fuel Economy: 28/39 MPG (city/hwy)\n"
                "- Safety: Toyota Safety Sense 3.0\n\n"
                "Answer using only the specifications above."
            ),
        },
        {
            "name": "ford-expert",
            "description": "Specialist in Ford F-150 specifications",
            "prompt": (
                "You are the Ford vehicle expert.\n\n"
                "Key Specifications (Ford F-150 2025):\n"
                "- Engine: 3.5L EcoBoost V6, 400 hp\n"
                "- Fuel Economy: 18/23 MPG (city/hwy)\n"
                "- Towing: 13,500 lbs\n\n"
                "Answer using only the specifications above."
            ),
        },
    ]
    seed_path = tmp_path / "fleet_seed.json"
    seed_path.write_text(json.dumps(seed))
    return str(seed_path)


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("car_dealer_fleet")
async def test_health(
    tmp_path,
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    seed_path = _seed_fleet(tmp_path)
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ORCHID_FLEET_SEED_PATH", seed_path)
        async with build_orchid_test_app(
            example="car_dealer_fleet",
            vector_store=in_memory_vector_store,
        ) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "ok"


@pytest.mark.example("car_dealer_fleet")
async def test_seeded_fleet_routes_to_toyota_expert(
    tmp_path,
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A Toyota question is routed to the toyota-expert specialist."""
    seed_path = _seed_fleet(tmp_path)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about Toyota Camry fuel economy",
        execution="sequential",
        agents=["toyota-expert"],
    )
    factory.add_text(
        "The Toyota Camry 2025 delivers 28 MPG in the city and 39 MPG on the highway."
    )

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ORCHID_FLEET_SEED_PATH", seed_path)
        async with build_orchid_test_app(
            example="car_dealer_fleet",
            vector_store=in_memory_vector_store,
            chat_model=factory.build(),
        ) as client:
            chat_id = _create_chat(client)
            data = _send_message(client, chat_id, "What is the Camry fuel economy?")
            assert data["response"]
            assert "39" in data["response"]


@pytest.mark.example("car_dealer_fleet")
async def test_seeded_fleet_routes_to_ford_expert(
    tmp_path,
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A Ford question is routed to the ford-expert specialist."""
    seed_path = _seed_fleet(tmp_path)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about Ford F-150 towing capacity",
        execution="sequential",
        agents=["ford-expert"],
    )
    factory.add_text("The Ford F-150 2025 can tow up to 13,500 lbs.")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ORCHID_FLEET_SEED_PATH", seed_path)
        async with build_orchid_test_app(
            example="car_dealer_fleet",
            vector_store=in_memory_vector_store,
            chat_model=factory.build(),
        ) as client:
            chat_id = _create_chat(client)
            data = _send_message(client, chat_id, "How much can the F-150 tow?")
            assert data["response"]
            assert "13,500" in data["response"]


@pytest.mark.example("car_dealer_fleet")
async def test_chat_history_with_fleet_agent(
    tmp_path,
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """Messages exchanged with a fleet expert are persisted."""
    seed_path = _seed_fleet(tmp_path)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about Toyota",
        execution="sequential",
        agents=["toyota-expert"],
    )
    factory.add_text("The Camry gets 28 MPG city and 39 MPG highway.")

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("ORCHID_FLEET_SEED_PATH", seed_path)
        async with build_orchid_test_app(
            example="car_dealer_fleet",
            vector_store=in_memory_vector_store,
            chat_model=factory.build(),
        ) as client:
            chat_id = _create_chat(client)
            _send_message(client, chat_id, "Tell me about the Camry.")

            resp = client.get(
                f"/chats/{chat_id}/messages",
                headers={"Authorization": "Bearer dev-token"},
            )
            assert resp.status_code == 200
            messages = resp.json()
            assert any("Camry" in m.get("content", "") for m in messages)
