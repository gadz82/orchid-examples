"""End-to-end Pollen/Bloom coverage for the event-driven pipeline example."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from orchid_ai.core.events.job import JobStatus
from orchid_ai.core.events.signal import Signal
from orchid_ai.core.events.store import OrchidScheduleRecord
from orchid_ai.core.state import OrchidAuthContext
from orchid_ai.events.producers.scheduler import SchedulerProducer
from orchid_ai.events.visibility import run_is_visible

from examples.data_pipeline_events.identity import DEMO_TENANT, DEMO_USER
from examples.data_pipeline_events.runtime import FacadePipelineRunner
from examples.data_pipeline_events.tests.conftest import INGEST_TOKEN, SOURCE_ID

HEADLINE = "Customer health is stable"


async def _process(harness) -> None:
    await harness.processor.process_until_idle(
        queue=harness.queue,
        signal_store=harness.storage.signals,
        triggers=harness.triggers,
        identity_resolver=harness.resolver,
        job_store=harness.storage.jobs,
        job_runner=harness.runner,
    )


def _signal_body(*, chat_id: str | None = None) -> dict:
    body = {
        "type": "pipeline.customer_health.requested",
        "tenant_key": DEMO_TENANT,
        "user_id": DEMO_USER,
        "payload": {"customer_id": "C-100"},
    }
    if chat_id is not None:
        body["chat_binding"] = {"chat_id": chat_id, "mode": "append_final_message"}
    return body


def _headers(token: str = INGEST_TOKEN, *, idempotency_key: str = "C-100:requested") -> dict:
    return {
        "x-orchid-source": SOURCE_ID,
        "authorization": f"Bearer {token}",
        "idempotency-key": idempotency_key,
        "content-type": "application/json",
    }


@pytest.mark.example("data_pipeline_events")
async def test_request_signal_runs_pipeline_and_posts_summary_to_chat(events_harness) -> None:
    response = events_harness.client.post(
        "/signals",
        content=json.dumps(_signal_body(chat_id=events_harness.chat.id)),
        headers=_headers(),
    )
    assert response.status_code == 202
    assert response.json()["signal_id"]

    await _process(events_harness)

    runs = list(await events_harness.storage.jobs.list())
    assert len(runs) == 1
    [run] = runs
    assert run.status == JobStatus.SUCCEEDED
    assert run.spec.target == "pipeline"
    assert run.spec.pipeline_name == "customer_health"
    assert run.spec.pipeline_input == {"customer_id": "C-100"}
    assert run.spec.visibility == "actor"
    assert run.spec.visibility_user_id == DEMO_USER
    assert run.result is not None
    assert run.result["status"] == "succeeded"
    assert run.result["pipeline"] == "customer_health"
    assert run.result["pipeline_run_id"]
    assert run.result["output"]["headline"] == HEADLINE
    assert run.result["final_response"] == HEADLINE
    assert run.result["graph_stats"]["relations"] == 2

    actor = await events_harness.resolver.mint_for_user(DEMO_TENANT, DEMO_USER)
    stranger = await events_harness.resolver.mint_for_user(DEMO_TENANT, "u-other")
    assert run_is_visible(run, actor) is True
    assert run_is_visible(run, stranger) is False

    messages = await events_harness.orchid.chat_repo.get_messages(events_harness.chat.id)
    assistant_messages = [message for message in messages if message.role == "assistant"]
    assert len(assistant_messages) == 1
    message = assistant_messages[0]
    assert message.content == HEADLINE
    assert message.agents_used == ["pipeline:customer_health"]
    assert message.metadata["origin"] == "bloom"
    assert message.metadata["trigger_id"] == "customer-health-request"
    assert message.metadata["pipeline"] == "customer_health"
    assert message.metadata["pipeline_run_id"] == run.result["pipeline_run_id"]

    sink = events_harness.orchid.runtime.signal_emitter
    assert sink is not None and len(sink.signals) == 1
    assert sink.signals[0].type == "pipeline.customer_health.completed"

    serialized = json.dumps(
        {
            "result": run.result,
            "input": run.spec.pipeline_input,
            "message": message.content,
            "metadata": message.metadata,
            "signal": {"payload": sink.signals[0].payload, "type": sink.signals[0].type},
        },
        default=str,
    )
    assert INGEST_TOKEN not in serialized


@pytest.mark.example("data_pipeline_events")
async def test_request_rejects_a_bad_bearer(events_harness) -> None:
    response = events_harness.client.post(
        "/signals",
        content=json.dumps(_signal_body()),
        headers=_headers(token="wrong-token"),
    )
    assert response.status_code == 401
    assert await events_harness.storage.jobs.list() == []


@pytest.mark.example("data_pipeline_events")
async def test_request_without_binding_runs_without_a_chat_message(events_harness) -> None:
    response = events_harness.client.post(
        "/signals",
        content=json.dumps(_signal_body()),
        headers=_headers(idempotency_key="C-100:no-binding"),
    )
    assert response.status_code == 202

    await _process(events_harness)

    [run] = list(await events_harness.storage.jobs.list())
    assert run.status == JobStatus.SUCCEEDED
    assert await events_harness.orchid.chat_repo.get_messages(events_harness.chat.id) == []


@pytest.mark.example("data_pipeline_events")
async def test_foreign_chat_binding_fails_before_running_the_pipeline(events_harness) -> None:
    foreign = await events_harness.orchid.chat_repo.create_chat(
        tenant_id=DEMO_TENANT,
        user_id="u-other",
        title="Somebody else's chat",
    )
    response = events_harness.client.post(
        "/signals",
        content=json.dumps(_signal_body(chat_id=foreign.id)),
        headers=_headers(idempotency_key="C-100:foreign-chat"),
    )
    assert response.status_code == 202

    await _process(events_harness)

    [run] = list(await events_harness.storage.jobs.list())
    assert run.status == JobStatus.FAILED
    assert run.result is None
    assert "ChatBindingForbiddenError" in (run.error or "")
    assert await events_harness.orchid.chat_repo.get_messages(foreign.id) == []


@pytest.mark.example("data_pipeline_events")
async def test_bloom_mode_is_forwarded_as_chat(events_harness) -> None:
    class _SpyOrchid:
        def __init__(self) -> None:
            self.kwargs: dict = {}

        async def run_pipeline(self, name, pipeline_input, **kwargs):
            self.kwargs = kwargs
            return {"status": "succeeded", "summary": "ok", "output": {}}

    spy = _SpyOrchid()
    adapter = FacadePipelineRunner(spy)  # type: ignore[arg-type]
    await adapter.run(
        "customer_health",
        {"customer_id": "C-1"},
        auth=None,
        mode="bloom",
        correlation_id="corr",
        chat_id="chat-1",
        include_graph=False,
    )
    assert spy.kwargs["mode"] == "chat"
    assert adapter.last_mode == "chat"


class FakeSchedulerBackend:
    """Capture APScheduler registrations and let the test fire them."""

    def __init__(self) -> None:
        self.jobs: dict[str, object] = {}

    async def start(self) -> None:
        return None

    async def shutdown(self, *, wait: bool = True) -> None:
        return None

    def add_cron(self, *, schedule_id: str, cron: str, callback, max_instances: int = 1) -> None:
        self.jobs[schedule_id] = callback

    def add_interval(
        self, *, schedule_id: str, seconds: int, callback, max_instances: int = 1, next_run_time=None
    ) -> None:
        self.jobs[schedule_id] = callback

    def remove(self, schedule_id: str) -> None:
        self.jobs.pop(schedule_id, None)

    def get_next_fire(self, schedule_id: str):
        return None


@pytest.mark.example("data_pipeline_events")
async def test_cron_schedule_runs_the_pipeline_for_the_service_account(events_harness) -> None:
    schedule = next(s for s in events_harness.config.events.schedules if s.id == "customer-health-daily")
    assert schedule.trigger_id == "customer-health-scheduled"
    assert schedule.cron == "0 6 * * *"
    await events_harness.storage.schedules.upsert(
        OrchidScheduleRecord(
            schedule_id=schedule.id,
            trigger_id=schedule.trigger_id,
            cron=schedule.cron,
            interval_seconds=schedule.interval_seconds,
            identity_claim=schedule.identity.model_dump(),
            last_fire_at=None,
            next_fire_at=None,
            enabled=True,
        )
    )
    backend = FakeSchedulerBackend()
    producer = SchedulerProducer(schedule_store=events_harness.storage.schedules, backend=backend)
    await producer.start(events_harness.dispatcher)
    try:
        assert "customer-health-daily" in backend.jobs
        await backend.jobs["customer-health-daily"]()
    finally:
        await producer.stop()

    await _process(events_harness)

    runs = list(await events_harness.storage.jobs.list())
    assert len(runs) == 1
    [run] = runs
    assert run.status == JobStatus.SUCCEEDED
    assert run.spec.trigger_id == "customer-health-scheduled"
    assert run.spec.pipeline_input == {"customer_id": "C-SCHEDULED"}
    assert run.spec.visibility == "tenant"
    assert run.result is not None
    assert run.result["output"]["headline"] == HEADLINE

    scheduler = await events_harness.resolver.resolve_service_account("scheduler")
    assert run_is_visible(run, scheduler) is True
    other_tenant = OrchidAuthContext(access_token="x", tenant_key="other", user_id="u-1")
    assert run_is_visible(run, other_tenant) is False
    assert await events_harness.orchid.chat_repo.get_messages(events_harness.chat.id) == []
    sink = events_harness.orchid.runtime.signal_emitter
    assert sink is not None and len(sink.signals) == 1


@pytest.mark.example("data_pipeline_events")
def test_trigger_config_builds_a_pipeline_job_spec(events_harness) -> None:
    trigger = events_harness.triggers.get("customer-health-request")
    assert trigger is not None
    assert trigger.visibility == "actor"
    assert trigger.respect_chat_binding is True

    now = datetime.now(UTC)
    signal = Signal(
        type="pipeline.customer_health.requested",
        payload={"customer_id": "C-7", "regions": [{"region": "north"}]},
        source="test",
        occurred_at=now,
        tenant_key=DEMO_TENANT,
        signal_id=uuid4(),
        persisted_at=now,
        user_id=DEMO_USER,
        chat_binding={"chat_id": "chat-1"},
    )
    spec = trigger.build_job_spec(signal)
    assert spec.target == "pipeline"
    assert spec.pipeline_name == "customer_health"
    assert spec.pipeline_input == {"customer_id": "C-7", "regions": [{"region": "north"}]}
    assert spec.chat_binding == {"chat_id": "chat-1"}
    assert spec.visibility == "actor"
    assert spec.visibility_user_id == DEMO_USER

    scheduled = events_harness.triggers.get("customer-health-scheduled")
    assert scheduled is not None
    assert scheduled.visibility == "tenant"
    cron_signal = Signal(
        type="cron",
        payload={"schedule_id": "customer-health-daily"},
        source="scheduler:customer-health-daily",
        occurred_at=now,
        tenant_key="default",
        signal_id=uuid4(),
        persisted_at=now,
    )
    scheduled_spec = scheduled.build_job_spec(cron_signal)
    assert scheduled_spec.pipeline_input == {"customer_id": "C-SCHEDULED"}


@pytest.mark.example("data_pipeline_events")
def test_example_declares_sqlite_events_and_a_scheduler(events_harness) -> None:
    events = events_harness.config.events
    assert events.enabled is True
    assert events.store is not None and events.store.class_path.endswith("SQLiteEventStorage")
    assert events.queue is not None and events.queue.class_path.endswith("SQLiteSignalQueue")
    assert any(producer.class_path.endswith("SchedulerProducer") for producer in events.producers)
    assert events.ingestion.sources[0].id == SOURCE_ID
