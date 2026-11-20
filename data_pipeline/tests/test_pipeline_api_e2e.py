"""HTTP e2e coverage for the direct data-pipeline example."""

from __future__ import annotations

import json

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.plugin import build_orchid_test_app

HEADERS = {"Authorization": "Bearer dev-token"}


def _factory() -> FakeChatModelFactory:
    factory = FakeChatModelFactory()
    factory.add_structured_response(risk="medium", score=42)
    factory.add_text("Escalation note: schedule a success review this week.")
    factory.add_structured_response(
        headline="Customer C-100 is stable",
        body="Retain the account and review usage next month.",
        risk="medium",
    )
    return factory


@pytest.mark.example("data_pipeline")
async def test_api_lists_and_runs_the_pipeline(in_memory_vector_store) -> None:
    async with build_orchid_test_app(
        example="data_pipeline",
        vector_store=in_memory_vector_store,
        chat_model=_factory().build(),
    ) as client:
        assert client.get("/health").status_code == 200

        listing = client.get("/pipelines", headers=HEADERS)
        assert listing.status_code == 200
        names = {item["name"] for item in listing.json()["items"]}
        assert names == {"account_snapshot", "customer_health"}

        validate = client.post(
            "/pipelines/customer_health/validate",
            json={"input": {"customer_id": "C-100"}},
            headers=HEADERS,
        )
        assert validate.status_code == 200
        assert validate.json() == {"valid": True, "errors": []}

        response = client.post(
            "/pipelines/customer_health/runs",
            json={
                "input": {
                    "customer_id": "C-100",
                    "regions": [{"region": "north"}, {"region": "south"}],
                },
                "include_graph": True,
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "succeeded"
        assert body["pipeline"] == "customer_health"
        assert body["output"]["headline"] == "Customer C-100 is stable"
        assert body["summary"] == "Customer C-100 is stable"
        assert body["graph_stats"]["relations"] == 2
        assert body["graph"]["objects"]
        assert {job["status"] for job in body["jobs"].values()} == {"succeeded"}


@pytest.mark.example("data_pipeline")
async def test_api_reports_input_validation_errors(in_memory_vector_store) -> None:
    async with build_orchid_test_app(
        example="data_pipeline",
        vector_store=in_memory_vector_store,
        chat_model=_factory().build(),
    ) as client:
        response = client.post(
            "/pipelines/customer_health/runs",
            json={"input": {"regions": [{"region": "north"}]}},
            headers=HEADERS,
        )
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "pipeline_input_schema_invalid"
        assert "customer_id" in str(error)


@pytest.mark.example("data_pipeline")
async def test_api_streams_pipeline_events(in_memory_vector_store) -> None:
    async with build_orchid_test_app(
        example="data_pipeline",
        vector_store=in_memory_vector_store,
        chat_model=_factory().build(),
    ) as client:
        response = client.post(
            "/pipelines/customer_health/runs/stream",
            json={"input": {"customer_id": "C-100"}},
            headers=HEADERS,
        )
        assert response.status_code == 200
        frames = [
            json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")
        ]
        types = [frame["type"] for frame in frames]
        assert types[0] == "pipeline.started"
        assert "pipeline.job.started" in types
        assert types[-1] == "pipeline.finished"
        final = frames[-1]["data"]
        assert final["status"] == "succeeded"
        assert final["result"]["output"]["headline"] == "Customer C-100 is stable"
