"""Phase-6 CI smoke test for ``examples/basketball/`` morning-trivia.

Drives the events runtime end-to-end without spinning up the full
``Orchid`` facade — just the dispatcher + processor + a fake
graph-invoker.  This keeps the test fast (≤1 s) and hermetic
(SQLite in-memory, no Ollama / Qdrant).

Verifies (per the §6 phase mapping in
``.knowledge/pollen-bloom-examples.md``):

- A scheduler cron tick produces a synthetic ``cron`` signal.
- The matching trigger fires under the ``trivia-bot`` service
  account (no ``mint_for_user`` involvement).
- The resulting :class:`JobRun` lands ``visibility='tenant'``
  (operational override per §26) with no ``visibility_user_id``.
- A non-admin caller in the same tenant CAN see the run via the
  visibility predicate; a non-admin in a different tenant CANNOT —
  the §26.6 cross-tenant boundary.
"""

from __future__ import annotations

import datetime as _dt
import uuid as _uuid
from pathlib import Path

import aiosqlite
import pytest

from examples.basketball.identity import BasketballIdentityResolver
from orchid_ai.config.schema_events import (
    OrchidScheduleConfig,
    OrchidTriggerConfig,
    OrchidTriggerEmitConfig,
    OrchidTriggerMatchConfig,
    ServiceAccountIdentity,
)
from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.core.events.job import JobStatus
from orchid_ai.core.events.signal import SignalEnvelope
from orchid_ai.core.events.store import OrchidScheduleRecord
from orchid_ai.core.state import OrchidAuthContext
from orchid_ai.events.backends.sqlite import SQLiteEventStorage
from orchid_ai.events.processors.asyncio_pool import AsyncioWorkerPoolProcessor
from orchid_ai.events.queues.sqlite import SQLiteSignalQueue
from orchid_ai.events.registry import build_registry_from_config
from orchid_ai.events.runners.graph_runner import GraphJobRunner
from orchid_ai.events.visibility import run_is_visible


@pytest.fixture
async def shared_db(tmp_path: Path):
    dsn = str(tmp_path / "basketball-events.db")
    conn = await aiosqlite.connect(dsn)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    storage = SQLiteEventStorage(conn=conn)
    await storage.init_db()
    queue = SQLiteSignalQueue(conn=conn)
    yield {"storage": storage, "queue": queue, "conn": conn}
    await conn.close()


async def _trivia_invoker(run, auth) -> dict:
    """Stand-in for the real graph: produces a deterministic 3-fact
    digest so the test asserts on shape, not LLM output."""
    return {
        "final_response": (
            "## NBA Trivia — yesterday's games\n\n"
            "1. Fact A — citation A\n"
            "2. Fact B — citation B\n"
            "3. Fact C — citation C\n"
        ),
        "agents_used": ["notifications"],
    }


async def test_morning_trivia_fires_and_completes(shared_db) -> None:
    """End-to-end: ingest a cron signal → processor matches the
    morning-trivia trigger → the GraphJobRunner produces a 3-fact
    digest → the JobRun is SUCCEEDED with visibility='tenant'."""
    storage = shared_db["storage"]
    queue = shared_db["queue"]

    # Build the trigger as it would be loaded from agents.yaml.
    trigger_cfg = OrchidTriggerConfig(
        id="morning-trivia",
        on=OrchidTriggerMatchConfig(signal="cron", cron="0 7 * * 1-5"),
        emits=OrchidTriggerEmitConfig(
            agent="notifications",
            prompt_template="Build the digest",
            identity=ServiceAccountIdentity(name="trivia-bot"),
            visibility="tenant",  # §26 — operational override
        ),
    )
    schedule_cfg = OrchidScheduleConfig(
        id="morning-trivia-cron",
        cron="0 7 * * 1-5",
        trigger_id="morning-trivia",
        identity=ServiceAccountIdentity(name="trivia-bot"),
    )
    await storage.schedules.upsert(
        OrchidScheduleRecord(
            schedule_id=schedule_cfg.id,
            trigger_id=schedule_cfg.trigger_id,
            cron=schedule_cfg.cron,
            interval_seconds=None,
            identity_claim=schedule_cfg.identity.model_dump(),
            last_fire_at=None,
            next_fire_at=None,
            enabled=True,
        )
    )

    registry = build_registry_from_config(
        [trigger_cfg], known_agents={"notifications"}
    )
    resolver = BasketballIdentityResolver()
    dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)
    runner = GraphJobRunner(invoker=_trivia_invoker)
    processor = AsyncioWorkerPoolProcessor()

    # Simulate the scheduler's cron-tick body — exactly the envelope
    # ``SchedulerProducer._make_callback`` would have produced.
    fire_iso = "2026-05-12T07:00:00+00:00"
    envelope = SignalEnvelope(
        type="cron",
        payload={"schedule_id": "morning-trivia-cron", "fire_time": fire_iso},
        source="scheduler:morning-trivia-cron",
        occurred_at=_dt.datetime.fromisoformat(fire_iso),
        tenant_key="basketball-demo",
        identity_claim={"mode": "service_account", "name": "trivia-bot"},
        dedupe_key=f"morning-trivia-cron:{fire_iso}",
    )
    await dispatcher.ingest(envelope)

    await processor.process_until_idle(
        queue=queue,
        signal_store=storage.signals,
        triggers=registry,
        identity_resolver=resolver,
        job_store=storage.jobs,
        job_runner=runner,
    )

    runs = await storage.jobs.list()
    assert len(runs) == 1
    [run] = runs
    assert run.status == JobStatus.SUCCEEDED
    assert run.spec.trigger_id == "morning-trivia"
    assert run.spec.visibility == "tenant"  # §26 operational override
    assert run.spec.visibility_user_id is None
    assert "Fact A" in (run.result or {}).get("final_response", "")


async def test_morning_trivia_run_visible_to_tenant_users(shared_db) -> None:
    """The §26 ``visibility=tenant`` override means any authenticated
    caller in the same tenant can see this digest run.  Cross-tenant
    callers cannot, even with the admin role."""
    storage = shared_db["storage"]
    queue = shared_db["queue"]

    # Build + run as in the previous test.
    trigger_cfg = OrchidTriggerConfig(
        id="morning-trivia",
        on=OrchidTriggerMatchConfig(signal="cron", cron="0 7 * * 1-5"),
        emits=OrchidTriggerEmitConfig(
            agent="notifications",
            prompt_template="x",
            identity=ServiceAccountIdentity(name="trivia-bot"),
            visibility="tenant",
        ),
    )
    registry = build_registry_from_config(
        [trigger_cfg], known_agents={"notifications"}
    )
    dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)

    await dispatcher.ingest(
        SignalEnvelope(
            type="cron",
            payload={},
            source="scheduler:morning-trivia-cron",
            occurred_at=_dt.datetime.now(tz=_dt.UTC),
            tenant_key="basketball-demo",
            identity_claim={"mode": "service_account", "name": "trivia-bot"},
            dedupe_key=f"sched:{_uuid.uuid4()}",
        )
    )
    await AsyncioWorkerPoolProcessor().process_until_idle(
        queue=queue,
        signal_store=storage.signals,
        triggers=registry,
        identity_resolver=BasketballIdentityResolver(),
        job_store=storage.jobs,
        job_runner=GraphJobRunner(invoker=_trivia_invoker),
    )

    [run] = await storage.jobs.list()

    # In-tenant non-admin → visible.
    same_tenant = OrchidAuthContext(
        access_token="t",
        tenant_key="basketball-demo",
        user_id="u-anyone",
    )
    assert run_is_visible(run, same_tenant) is True

    # Cross-tenant admin → NOT visible (§26.6 cross-tenant boundary).
    other_tenant_admin = OrchidAuthContext(
        access_token="t",
        tenant_key="other-tenant",
        user_id="u-admin",
        roles={"admin"},
    )
    assert run_is_visible(run, other_tenant_admin) is False


def test_act_as_user_trigger_rejected_at_boot_for_basketball() -> None:
    """The basketball example's resolver doesn't implement
    :meth:`mint_for_user` (it uses service_account only).  An
    ``act_as_user`` trigger added by mistake MUST fail at boot via
    the registry's mint probe — naming the resolver class and the
    trigger id.

    This is the deterministic-misconfiguration-detection §13 calls
    for: every basketball deployment can't accidentally enable a
    Bloom whose identity flavour the resolver doesn't support.
    """
    from orchid_ai.config.schema_events import ActAsUserIdentity
    from orchid_ai.core.events.errors import TriggerRegistrationError

    bad_trigger = OrchidTriggerConfig(
        id="ticket-triage",
        on=OrchidTriggerMatchConfig(signal="support.ticket.created"),
        emits=OrchidTriggerEmitConfig(
            agent="notifications",
            prompt_template="x",
            identity=ActAsUserIdentity(user_id_from="signal.user_id"),
        ),
    )
    with pytest.raises(TriggerRegistrationError) as exc_info:
        build_registry_from_config(
            [bad_trigger],
            known_agents={"notifications"},
            identity_resolver=BasketballIdentityResolver(),
        )
    msg = str(exc_info.value)
    assert "ticket-triage" in msg
    assert "BasketballIdentityResolver" in msg
