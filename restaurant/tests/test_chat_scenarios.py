"""API-level e2e scenarios for the restaurant example.

These tests drive the example through orchid-api using the shared
in-process app builder. They cover routing, RAG, custom agents,
document upload, and orchestrator skills.
"""

from __future__ import annotations

import pytest
from orchid_ai.core.repository import OrchidDocument

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.fixtures.mock_vector import InMemoryVectorStore, seed_documents
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


def _seed_menu(store: InMemoryVectorStore) -> None:
    """Populate the in-memory vector store with menu RAG documents."""
    docs = [
        OrchidDocument(
            page_content="Margherita Pizza: tomato sauce, mozzarella, fresh basil.",
            id="menu-1",
            metadata={"category": "pizza", "dietary": "vegetarian"},
        ),
        OrchidDocument(
            page_content="Vegan Buddha Bowl: quinoa, roasted chickpeas, avocado, sweet potato.",
            id="menu-2",
            metadata={"category": "bowl", "dietary": "vegan"},
        ),
        OrchidDocument(
            page_content="Filet Mignon: beef tenderloin with red wine reduction.",
            id="menu-3",
            metadata={"category": "steak"},
        ),
    ]
    seed_documents(store, "menu", docs)


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("restaurant/config")
async def test_menu_agent_responds_to_menu_query(in_memory_vector_store) -> None:
    """A menu question is routed to the menu agent and returns an answer."""
    _seed_menu(in_memory_vector_store)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about menu",
        execution="parallel",
        agents=["menu"],
    )
    factory.add_text("We have a delicious Margherita Pizza with fresh basil.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What's on the menu?")
        assert data["response"]
        assert "Margherita" in data["response"]


@pytest.mark.example("restaurant/config")
async def test_orders_agent_handles_order_status(in_memory_vector_store) -> None:
    """An order-related question is routed to the orders agent."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about an order",
        execution="parallel",
        agents=["orders"],
    )
    factory.add_text("Order ORD-123 is being prepared and will be ready in 15 minutes.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What's the status of order ORD-123?")
        assert data["response"]
        assert "ORD-123" in data["response"]


@pytest.mark.example("restaurant/config")
async def test_reviews_custom_agent_analyzes_feedback(in_memory_vector_store) -> None:
    """A review-analysis question routes to the custom ReviewsAgent."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants review analysis",
        execution="parallel",
        agents=["reviews"],
    )
    factory.add_text("The review is positive — 4.5 stars with praise for service.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Analyze this review: food was great")
        assert data["response"]
        assert "positive" in data["response"].lower()


@pytest.mark.example("restaurant/config")
async def test_document_upload_indexes_menu(tmp_path, in_memory_vector_store) -> None:
    """Uploading a text document indexes it into the vector store."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User uploads a document",
        execution="parallel",
        agents=["menu"],
    )
    factory.add_text("Menu document received and indexed.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        menu_file = tmp_path / "menu.txt"
        menu_file.write_text("New seasonal pumpkin ravioli with sage butter.")

        with menu_file.open("rb") as f:
            resp = client.post(
                f"/chats/{chat_id}/upload",
                files={"files": ("menu.txt", f, "text/plain")},
                headers={"Authorization": "Bearer dev-token"},
            )
        assert resp.status_code == 200
        upload_data = resp.json()
        assert upload_data.get("status") in ("indexed", "ok", "success")

        # The upload namespace should now contain at least one document.
        assert "uploads" in in_memory_vector_store.docs
        assert len(in_memory_vector_store.docs["uploads"]) >= 1


@pytest.mark.example("restaurant/config")
async def test_multi_query_retrieval_finds_diverse_menu_items(in_memory_vector_store) -> None:
    """A broad query retrieves multiple menu items from the seeded vector store."""
    _seed_menu(in_memory_vector_store)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants vegetarian options",
        execution="parallel",
        agents=["menu"],
    )
    factory.add_text("Vegetarian options include Margherita Pizza and Vegan Buddha Bowl.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What vegetarian dishes do you have?")
        assert data["response"]
        assert "vegetarian" in data["response"].lower()


@pytest.mark.example("restaurant/config")
async def test_orchestrator_skill_chains_agents(in_memory_vector_store) -> None:
    """An orchestrator-level skill can be invoked via a structured routing decision."""
    _seed_menu(in_memory_vector_store)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants full dining experience",
        execution="skill",
        skill="full_dining_experience",
    )
    # Skill expansion creates a sequential pipeline; provide a response
    # for each agent step (menu, orders, reviews).
    for _ in range(3):
        factory.add_text("Step completed for the full dining experience.")

    async with build_orchid_test_app(
        example="restaurant/config",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Plan a full dining experience for me")
        assert data["response"]
        assert "dining" in data["response"].lower()
