"""Direct-facade e2e coverage for the customer-health data pipeline.

The pipeline runs in-process with a deterministic chat model: no API key, no
Ollama, no network. Every job kind is exercised, including the emit job backed
by the example's local signal sink.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from orchid_ai import Orchid
from orchid_ai.core.pipeline import OrchidPipelineInputError

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory

EXAMPLE = Path(__file__).resolve().parents[1]
INPUT = {
    "customer_id": "C-100",
    "regions": [{"region": "north"}, {"region": "south"}],
}


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


async def _run(*, input: dict | None = None) -> tuple[Orchid, object]:
    factory = _factory()
    orchid = await Orchid.from_config_path(
        str(EXAMPLE / "orchid.yml"),
        apply_yaml=True,
        agents_config_path=str(EXAMPLE / "agents.yaml"),
        chat_storage_class="memory",
        runtime_overrides={"chat_model": factory.build()},
    )
    result = await orchid.run_pipeline(
        "customer_health",
        input if input is not None else INPUT,
        user_id="u-1",
        tenant_id="t-1",
        include_graph=True,
    )
    return orchid, result


@pytest.mark.example("data_pipeline")
async def test_pipeline_runs_every_job_kind_and_a_typed_output() -> None:
    orchid, result = await _run()
    try:
        assert result.status == "succeeded"
        assert result.error is None
        assert result.output == {
            "headline": "Customer C-100 is stable",
            "body": "Retain the account and review usage next month.",
            "risk": "medium",
        }
        assert result.summary == "Customer C-100 is stable"

        statuses = {job_id: payload["status"] for job_id, payload in result.jobs.items()}
        assert set(statuses) == {
            "load_account",
            "usage_map",
            "assess",
            "route",
            "propose",
            "escalate",
            "snapshot",
            "report",
            "notify",
        }
        assert set(statuses.values()) == {"succeeded"}

        kinds = {payload["kind"] for payload in result.jobs.values()}
        assert kinds == {"deterministic", "map", "llm", "decision", "agent", "subpipeline", "emit"}

        route = result.jobs["route"]["output"]
        assert route["label"] == "retain"
        assert route["confidence"] == 0.95
        assert "decision model 'route'" in route["rationale"]

        usage_items = result.jobs["usage_map"]["output"]["items"]
        assert set(usage_items) == {"usage_map#0", "usage_map#1"}
        assert [item["region"] for item in usage_items.values()] == ["north", "south"]

        assert result.graph_stats["objects"] == 7
        assert result.graph_stats["relations"] == 2
        assert result.graph_stats["by_type"]["Usage"] == 2
        assert result.graph_stats["by_type"]["Report"] == 1
        assert result.graph_stats["llm_calls"] == 3

        sink = orchid.runtime.signal_emitter
        assert sink is not None and len(sink.signals) == 1
        assert sink.signals[0].type == "pipeline.customer_health.completed"
        assert sink.signals[0].payload["customer_id"] == "C-100"
        assert sink.signals[0].dedupe_key == "customer-health:C-100"
    finally:
        await orchid.close()


@pytest.mark.example("data_pipeline")
async def test_pipeline_input_defaults_are_applied() -> None:
    orchid, result = await _run(input={"customer_id": "C-100"})
    try:
        assert result.status == "succeeded"
        assert result.output is not None
        assert result.output["headline"] == "Customer C-100 is stable"
        assert result.jobs["usage_map"]["output"]["items"]
    finally:
        await orchid.close()


@pytest.mark.example("data_pipeline")
async def test_pipeline_rejects_invalid_input() -> None:
    factory = _factory()
    orchid = await Orchid.from_config_path(
        str(EXAMPLE / "orchid.yml"),
        apply_yaml=True,
        agents_config_path=str(EXAMPLE / "agents.yaml"),
        chat_storage_class="memory",
        runtime_overrides={"chat_model": factory.build()},
    )
    try:
        with pytest.raises(OrchidPipelineInputError) as excinfo:
            await orchid.run_pipeline(
                "customer_health",
                {"regions": [{"region": "north"}]},
                user_id="u-1",
                tenant_id="t-1",
            )
        assert "customer_id" in str(excinfo.value)
    finally:
        await orchid.close()
