"""Phase-6 CI smoke test for ``examples/learning/`` weekly digest.

Exercises:

- Custom ``OrchidSignalProducer`` (``WeeklyDigestFanoutProducer``)
  that emits one signal per active learner per tenant.
- ``addressed_to_user`` identity: each Bloom runs under the
  ``digest-bot`` service account but is tagged with the addressed
  user via :func:`resolve_user_id_for_signal`.
- §26 default visibility ``addressed`` on each :class:`JobRun`,
  isolating per-user digests even though they share a producer.
- ``parallelism: per_user`` serialisation: two distinct users
  produce two distinct ``parallelism_key`` values, so they run in
  parallel rather than serialising on a single lock.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import aiosqlite
import pytest

from examples.learning.identity import LearningIdentityResolver
from examples.learning.producers.weekly_digest import (
    StaticTenantProvider,
    StaticUserLister,
    WeeklyDigestFanoutProducer,
)
from orchid_ai.config.schema_events import (
    AddressedToUserIdentity,
    OrchidTriggerConfig,
    OrchidTriggerEmitConfig,
    OrchidTriggerMatchConfig,
)
from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.core.events.job import JobStatus
from orchid_ai.events.backends.sqlite import SQLiteEventStorage
from orchid_ai.events.processors.asyncio_pool import AsyncioWorkerPoolProcessor
from orchid_ai.events.queues.sqlite import SQLiteSignalQueue
from orchid_ai.events.registry import build_registry_from_config
from orchid_ai.events.runners.graph_runner import GraphJobRunner


@pytest.fixture
async def learning_app(tmp_path: Path):
    dsn = str(tmp_path / "learning-events.db")
    conn = await aiosqlite.connect(dsn)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    storage = SQLiteEventStorage(conn=conn)
    await storage.init_db()
    queue = SQLiteSignalQueue(conn=conn)

    trigger = OrchidTriggerConfig(
        id="weekly-digest",
        on=OrchidTriggerMatchConfig(signal="weekly-digest.due"),
        emits=OrchidTriggerEmitConfig(
            agent="digest",
            prompt_template=(
                "Build digest for user {{user_id}} in {{tenant_key}}"
            ),
            identity=AddressedToUserIdentity(
                service_account="digest-bot",
                user_id_from="signal.user_id",
            ),
        ),
    )
    resolver = LearningIdentityResolver()
    resolver.seed("u-alice", token="t:alice")
    resolver.seed("u-bob", token="t:bob")
    registry = build_registry_from_config(
        [trigger], known_agents={"digest"}, identity_resolver=resolver
    )
    dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)

    async def _digest_invoker(run, auth) -> dict:
        return {
            "final_response": (
                f"## Weekly digest\n\nUser: "
                f"{auth.extra.get('addressed_user_id', '<no-user>')}\n"
                f"Service: {auth.extra.get('service_account', '<no-svc>')}\n"
            )
        }

    runner = GraphJobRunner(invoker=_digest_invoker)
    processor = AsyncioWorkerPoolProcessor()

    yield {
        "storage": storage,
        "queue": queue,
        "registry": registry,
        "resolver": resolver,
        "dispatcher": dispatcher,
        "runner": runner,
        "processor": processor,
    }
    await conn.close()


# ── Fan-out: one signal per (tenant, user) ──────────────────


async def test_fanout_emits_one_signal_per_active_user(learning_app) -> None:
    """A single fan-out tick emits N signals (one per active user)
    and the dispatcher persists each.  Subsequent ticks within the
    same ISO week are deduplicated by
    ``weekly-digest:<tenant>:<user>:<week>`` so a re-firing of the
    cron tick is harmless."""
    fanout = WeeklyDigestFanoutProducer(
        tenant_provider=StaticTenantProvider(["learning-demo"]),
        user_lister=StaticUserLister(
            {"learning-demo": ["u-alice", "u-bob"]}
        ),
        clock=lambda: _dt.datetime(2026, 5, 4, 6, 0, 0, tzinfo=_dt.UTC),
    )
    await fanout.start(learning_app["dispatcher"])

    emitted = await fanout.fanout_now()
    assert emitted == 2
    signals = await learning_app["storage"].signals.list()
    assert len(signals) == 2
    assert {s.user_id for s in signals} == {"u-alice", "u-bob"}

    # Re-fire (same week) is deduplicated.
    emitted_again = await fanout.fanout_now()
    assert emitted_again == 2  # the producer ingests; dispatcher dedupes
    signals_after = await learning_app["storage"].signals.list()
    assert len(signals_after) == 2  # still 2, not 4

    await fanout.stop()


# ── End-to-end: fan-out → addressed_to_user runs ────────────


async def test_fanout_produces_per_user_runs_with_addressed_visibility(
    learning_app,
) -> None:
    """One cron tick → N signals → N runs, each tagged with the
    addressed user and §26 default visibility ``addressed``."""
    fanout = WeeklyDigestFanoutProducer(
        tenant_provider=StaticTenantProvider(["learning-demo"]),
        user_lister=StaticUserLister(
            {"learning-demo": ["u-alice", "u-bob"]}
        ),
        clock=lambda: _dt.datetime(2026, 5, 4, 6, 0, 0, tzinfo=_dt.UTC),
    )
    await fanout.start(learning_app["dispatcher"])
    await fanout.fanout_now()
    await fanout.stop()

    await learning_app["processor"].process_until_idle(
        queue=learning_app["queue"],
        signal_store=learning_app["storage"].signals,
        triggers=learning_app["registry"],
        identity_resolver=learning_app["resolver"],
        job_store=learning_app["storage"].jobs,
        job_runner=learning_app["runner"],
    )

    runs = await learning_app["storage"].jobs.list()
    assert len(runs) == 2
    assert all(r.status == JobStatus.SUCCEEDED for r in runs)
    assert all(r.spec.visibility == "addressed" for r in runs)
    assert {r.spec.visibility_user_id for r in runs} == {"u-alice", "u-bob"}
    # Each run produced output bound to the addressed user (the
    # invoker echoes ``auth.extra['addressed_user_id']`` back, which
    # the processor populates per §12 step 3).
    user_outputs = {
        r.spec.visibility_user_id: (r.result or {}).get("final_response", "")
        for r in runs
    }
    assert "u-alice" in user_outputs["u-alice"]
    assert "u-bob" in user_outputs["u-bob"]


async def test_fanout_per_user_parallelism_keys_are_distinct(learning_app) -> None:
    """Two distinct users produce two distinct ``parallelism_key``
    values — exercising the §12 per-user lock that lets the
    processor run them in parallel rather than serialising on a
    shared key."""
    fanout = WeeklyDigestFanoutProducer(
        tenant_provider=StaticTenantProvider(["learning-demo"]),
        user_lister=StaticUserLister(
            {"learning-demo": ["u-alice", "u-bob"]}
        ),
    )
    await fanout.start(learning_app["dispatcher"])
    await fanout.fanout_now()
    await fanout.stop()
    await learning_app["processor"].process_until_idle(
        queue=learning_app["queue"],
        signal_store=learning_app["storage"].signals,
        triggers=learning_app["registry"],
        identity_resolver=learning_app["resolver"],
        job_store=learning_app["storage"].jobs,
        job_runner=learning_app["runner"],
    )
    runs = await learning_app["storage"].jobs.list()
    keys = {r.spec.parallelism_key for r in runs}
    assert len(keys) == 2  # one per user
