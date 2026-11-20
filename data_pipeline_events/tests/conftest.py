"""Hermetic event harness for the event-driven pipeline example."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from orchid_ai import Orchid
from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.events.bootstrap import build_signal_source_registry
from orchid_ai.events.processors.asyncio_pool import AsyncioWorkerPoolProcessor
from orchid_ai.events.registry import build_registry_from_config
from orchid_ai.events.runners.dispatch_runner import DispatchJobRunner
from orchid_ai.events.runners.pipeline_runner import PipelineJobRunner
from orchid_api.events.producers.http import HTTPIngestionProducer
from orchid_storage_sqlite.event_queue import SQLiteSignalQueue
from orchid_storage_sqlite.event_storage import SQLiteEventStorage

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples.data_pipeline_events.identity import DEMO_TENANT, DEMO_USER, PipelineIdentityResolver
from examples.data_pipeline_events.runtime import FacadePipelineRunner

EXAMPLE = Path(__file__).resolve().parents[1]
INGEST_TOKEN = "test-ingest-token"
SOURCE_ID = "customer-health-webhook"


def _factory() -> FakeChatModelFactory:
    factory = FakeChatModelFactory()
    factory.add_structured_response(risk="medium", score=42)
    factory.add_text("Escalation note: schedule a success review this week.")
    factory.add_structured_response(
        headline="Customer health is stable",
        body="Retain the account and review usage next month.",
        risk="medium",
    )
    return factory


@pytest.fixture
async def events_harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[SimpleNamespace]:
    monkeypatch.setenv("PIPELINE_INGEST_TOKEN", INGEST_TOKEN)

    orchid = await Orchid.from_config_path(
        str(EXAMPLE / "orchid.yml"),
        apply_yaml=True,
        agents_config_path=str(EXAMPLE / "agents.yaml"),
        chat_storage_class="memory",
        runtime_overrides={"chat_model": _factory().build()},
    )
    conn = await aiosqlite.connect(str(tmp_path / "events.db"))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    storage = SQLiteEventStorage(conn=conn)
    await storage.init_db()
    queue = SQLiteSignalQueue(conn=conn)

    resolver = PipelineIdentityResolver()
    config = orchid.config
    pipelines = orchid.pipelines
    assert pipelines is not None
    triggers = build_registry_from_config(
        config.events.triggers,
        known_agents=set(config.agents),
        known_pipelines=set(pipelines.names()),
        identity_resolver=resolver,
    )

    dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)
    runner = DispatchJobRunner(
        runners={
            "pipeline": PipelineJobRunner(
                pipeline_runner=FacadePipelineRunner(orchid),
                chat_storage=orchid.chat_repo,
            )
        }
    )
    processor = AsyncioWorkerPoolProcessor(concurrency=1, poll_interval_ms=10, lease_seconds=30)

    producer = HTTPIngestionProducer(registry=build_signal_source_registry(config.events.ingestion.sources))
    await producer.start(dispatcher)
    app = FastAPI()
    app.include_router(producer.router)
    client = TestClient(app)

    chat = await orchid.chat_repo.create_chat(
        tenant_id=DEMO_TENANT,
        user_id=DEMO_USER,
        title="Customer health",
    )

    harness = SimpleNamespace(
        orchid=orchid,
        storage=storage,
        queue=queue,
        triggers=triggers,
        resolver=resolver,
        dispatcher=dispatcher,
        processor=processor,
        runner=runner,
        client=client,
        chat=chat,
        config=config,
    )
    try:
        yield harness
    finally:
        await producer.stop()
        client.close()
        await orchid.close()
        await conn.close()
