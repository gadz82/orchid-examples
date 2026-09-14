"""API-level e2e smoke tests for the education example.

These complement the existing tool-level tests by driving the example
through orchid-api using the shared in-process app builder.
"""

from __future__ import annotations

import pytest
from orchid_ai.core.repository import OrchidDocument

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.fixtures.mock_vector import InMemoryVectorStore, seed_documents
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


def _seed_source(store: InMemoryVectorStore) -> None:
    seed_documents(
        store,
        "education-source",
        [
            OrchidDocument(
                page_content="Photosynthesis converts light energy into chemical energy.",
                id="edu-1",
            ),
        ],
    )


@pytest.mark.example("education")
async def test_health_endpoint() -> None:
    async with build_orchid_test_app(example="education") as client:
        resp = client.get("/health")
        assert resp.status_code == 200


@pytest.mark.example("education")
async def test_create_chat() -> None:
    async with build_orchid_test_app(example="education") as client:
        chat_id = _create_chat(client)
        assert chat_id


@pytest.mark.example("education")
async def test_content_analyzer_responds_to_short_query(in_memory_vector_store) -> None:
    """A short educational query routes to the content analyzer and returns a response."""
    _seed_source(in_memory_vector_store)
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User asks about educational content",
        execution="parallel",
        agents=["content-analyzer"],
    )
    factory.add_tool_calls(
        [
            {
                "name": "extract_concepts",
                "args": {"source_text": "photosynthesis"},
                "id": "tc1",
            }
        ]
    )
    factory.add_text("Key concept: photosynthesis turns light into chemical energy.")

    async with build_orchid_test_app(
        example="education",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "What is photosynthesis?")
        assert data["response"]
        assert "photosynthesis" in data["response"].lower()


@pytest.mark.example("education")
async def test_document_upload_indexes_source(tmp_path, in_memory_vector_store) -> None:
    """Uploading a text document indexes it into the education uploads namespace."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User uploads material",
        execution="parallel",
        agents=["content-analyzer"],
    )
    factory.add_text("Document indexed.")

    async with build_orchid_test_app(
        example="education",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
    ) as client:
        chat_id = _create_chat(client)
        source_file = tmp_path / "lesson.txt"
        source_file.write_text("Mitochondria are the powerhouses of the cell.")

        with source_file.open("rb") as f:
            resp = client.post(
                f"/chats/{chat_id}/upload",
                files={"files": ("lesson.txt", f, "text/plain")},
                headers={"Authorization": "Bearer dev-token"},
            )
        assert resp.status_code == 200
        upload_data = resp.json()
        assert upload_data["status"] == "ok"

        assert "education-uploads" in in_memory_vector_store.docs
        assert len(in_memory_vector_store.docs["education-uploads"]) >= 1
