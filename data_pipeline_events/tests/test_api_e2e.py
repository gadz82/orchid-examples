"""API-level e2e coverage for the event-driven pipeline example.

Boots the real orchid-api app with the example YAML, the SQLite event backend,
the scheduler producer, the HTTP ingestion producer and a deterministic chat
model, then drives one webhook through the production Bloom adapter.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.plugin import build_orchid_test_app

HEADERS = {"Authorization": "Bearer dev-token"}
INGEST_TOKEN = "test-ingest-token"
SOURCE_ID = "customer-health-webhook"
HEADLINE = "Customer health is stable"


def _factory() -> FakeChatModelFactory:
    factory = FakeChatModelFactory()
    factory.add_structured_response(risk="medium", score=42)
    factory.add_text("Escalation note: schedule a success review this week.")
    factory.add_structured_response(
        headline=HEADLINE,
        body="Retain the account and review usage next month.",
        risk="medium",
    )
    return factory


async def _wait_for_run(client) -> dict:
    for _ in range(80):
        response = client.get("/runs", headers=HEADERS)
        assert response.status_code == 200
        items = response.json().get("items", [])
        if items and items[0]["status"] not in ("queued", "running", "retry_scheduled"):
            return items[0]
        await asyncio.sleep(0.1)
    raise AssertionError("the Bloom run did not finish in time")


@pytest.mark.example("data_pipeline_events")
async def test_api_webhook_runs_the_pipeline_and_posts_to_the_bound_chat(in_memory_vector_store) -> None:
    async with build_orchid_test_app(
        example="data_pipeline_events",
        vector_store=in_memory_vector_store,
        chat_model=_factory().build(),
        include_event_router=True,
        extra_env={
            "DEV_AUTH_BYPASS": "false",
            "IDENTITY_RESOLVER_CLASS": "examples.data_pipeline_events.identity.PipelineIdentityResolver",
            "PIPELINE_INGEST_TOKEN": INGEST_TOKEN,
        },
    ) as client:
        assert client.get("/health").status_code == 200

        chat = client.post("/chats", json={}, headers=HEADERS)
        assert chat.status_code == 200
        chat_id = chat.json()["id"]

        body = {
            "type": "pipeline.customer_health.requested",
            "tenant_key": "data-pipeline-demo",
            "user_id": "dev-user",
            "payload": {"customer_id": "C-100"},
            "chat_binding": {"chat_id": chat_id, "mode": "append_final_message"},
        }
        signal = client.post(
            "/signals",
            content=json.dumps(body),
            headers={
                "x-orchid-source": SOURCE_ID,
                "authorization": f"Bearer {INGEST_TOKEN}",
                "idempotency-key": "C-100:api-e2e",
                "content-type": "application/json",
            },
        )
        assert signal.status_code == 202

        run = await _wait_for_run(client)
        assert run["status"] == "succeeded"
        assert run["trigger_id"] == "customer-health-request"
        assert run["visibility"] == "actor"
        assert run["visibility_user_id"] == "dev-user"

        detail = client.get(f"/runs/{run['run_id']}", headers=HEADERS)
        assert detail.status_code == 200
        result = detail.json()["result"]
        assert result["pipeline"] == "customer_health"
        assert result["output"]["headline"] == HEADLINE
        assert result["final_response"] == HEADLINE
        assert result["graph_stats"]["relations"] == 2

        messages = client.get(f"/chats/{chat_id}/messages", headers=HEADERS)
        assert messages.status_code == 200
        [message] = messages.json()
        assert message["content"] == HEADLINE
        assert message["agents_used"] == ["pipeline:customer_health"]
        assert message["metadata"]["origin"] == "bloom"
        assert message["metadata"]["pipeline_run_id"] == result["pipeline_run_id"]

        serialized = json.dumps({"result": result, "message": message}, default=str)
        assert INGEST_TOKEN not in serialized
