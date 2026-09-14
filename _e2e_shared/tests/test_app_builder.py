"""Self-test for the in-process orchid-api app builder."""

from __future__ import annotations

import pytest
from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.plugin import build_orchid_test_app


@pytest.mark.example("_e2e_shared/data/minimal-example")
async def test_build_minimal_app(in_memory_vector_store) -> None:
    async with build_orchid_test_app(
        example="_e2e_shared/data/minimal-example",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("ok", "healthy", "ready") or "graph_ready" in data


@pytest.mark.example("_e2e_shared/data/minimal-example")
async def test_minimal_app_create_chat(in_memory_vector_store) -> None:
    async with build_orchid_test_app(
        example="_e2e_shared/data/minimal-example",
        vector_store=in_memory_vector_store,
    ) as client:
        resp = client.post(
            "/chats",
            json={},
            headers={"Authorization": "Bearer dev-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data


@pytest.mark.example("_e2e_shared/data/minimal-example")
async def test_minimal_app_send_message(in_memory_vector_store) -> None:
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants a greeting",
        execution="parallel",
        agents=["greeter"],
    )
    factory.add_text("Hello from fake model")
    factory.add_text("Hello from fake synthesizer")
    with factory.patch():
        async with build_orchid_test_app(
            example="_e2e_shared/data/minimal-example",
            vector_store=in_memory_vector_store,
            chat_model=factory.build(),
        ) as client:
            chat = client.post(
                "/chats",
                json={},
                headers={"Authorization": "Bearer dev-token"},
            ).json()
            resp = client.post(
                f"/chats/{chat['id']}/messages",
                data={"message": "say hello"},
                headers={"Authorization": "Bearer dev-token"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "response" in data
            assert data["response"]


@pytest.mark.example("restaurant/config")
async def test_fake_chat_model_used_for_per_agent_llm(in_memory_vector_store) -> None:
    """Regression: agents whose YAML ``llm.model`` differs from the runtime
    default must still receive the injected fake model, not a newly-built
    real model.
    """
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about menu",
        execution="parallel",
        agents=["menu"],
    )
    factory.add_text("Vegetarian options include Margherita Pizza.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat = client.post(
            "/chats",
            json={},
            headers={"Authorization": "Bearer dev-token"},
        ).json()
        resp = client.post(
            f"/chats/{chat['id']}/messages",
            data={"message": "What vegetarian dishes do you have?"},
            headers={"Authorization": "Bearer dev-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "Margherita Pizza" in data["response"]
