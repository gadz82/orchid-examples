"""Phase-6 CI smoke tests for ``examples/helpdesk/``.

Three scenarios per ``.knowledge/pollen-bloom-examples.md`` §2:

1. A high-priority webhook is signed correctly, ingested by the
   :class:`HTTPIngestionProducer`, matches the
   ``high-priority-ticket`` trigger via the JMESPath ``when:`` filter,
   and produces a SUCCEEDED :class:`JobRun` whose
   ``visibility_user_id`` is the ticket reporter.
2. A low-priority webhook is ingested and persisted as a signal but
   the ``when:`` filter excludes it, so no :class:`JobRun` is
   created.
3. A trigger configured as ``act_as_user`` against a resolver that
   doesn't implement minting is rejected at boot — verifying the
   §13 deterministic-misconfiguration-detection contract.

Tests run against the SQLite + in-memory backend so the suite is
hermetic.  Postgres path is exercised in
``orchid/tests/events/test_postgres_queue.py`` already.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from examples.helpdesk.identity import HelpdeskIdentityResolver
from orchid_ai.config.schema_events import (
    ActAsUserIdentity,
    OrchidTriggerConfig,
    OrchidTriggerEmitConfig,
    OrchidTriggerMatchConfig,
)
from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.core.events.job import JobStatus
from orchid_ai.events.auth import HMACValidator
from orchid_ai.events.backends.sqlite import SQLiteEventStorage
from orchid_ai.events.processors.asyncio_pool import AsyncioWorkerPoolProcessor
from orchid_ai.events.ingestion import SignalSource, SignalSourceRegistry
from orchid_api.events.producers.http import HTTPIngestionProducer
from orchid_ai.events.queues.sqlite import SQLiteSignalQueue
from orchid_ai.events.registry import build_registry_from_config
from orchid_ai.events.runners.graph_runner import GraphJobRunner


_HMAC_SECRET = "test-secret-do-not-use-in-prod"


def _sign(body: bytes) -> str:
    return "sha256=" + _hmac.new(
        _HMAC_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()


@pytest.fixture
async def helpdesk_app(tmp_path):
    """Build the events runtime + a FastAPI app with the
    :class:`HTTPIngestionProducer` mounted, mirroring the production
    lifecycle minus the orchid-api wrapper."""
    dsn = str(tmp_path / "helpdesk-events.db")
    conn = await aiosqlite.connect(dsn)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    storage = SQLiteEventStorage(conn=conn)
    await storage.init_db()
    queue = SQLiteSignalQueue(conn=conn)

    trigger = OrchidTriggerConfig(
        id="high-priority-ticket",
        on=OrchidTriggerMatchConfig(
            signal="support.ticket.created",
            when="payload.priority == 'high'",
        ),
        emits=OrchidTriggerEmitConfig(
            agent="support",
            prompt_template="Triage ticket {{payload.ticket_id}}",
            identity=ActAsUserIdentity(user_id_from="signal.user_id"),
        ),
    )
    resolver = HelpdeskIdentityResolver()
    resolver.seed("u-test-1", token="user-token-u-test-1")
    registry = build_registry_from_config(
        [trigger], known_agents={"support"}, identity_resolver=resolver
    )
    dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)

    sources = [
        SignalSource(
            source_id="ticketing-system",
            validator=HMACValidator(secret=_HMAC_SECRET),
            allowed_types=frozenset(
                {"support.ticket.created", "support.ticket.updated"}
            ),
        )
    ]
    producer = HTTPIngestionProducer(registry=SignalSourceRegistry(sources))
    await producer.start(dispatcher)

    app = FastAPI()
    app.include_router(producer.router)

    async def _invoker(run, auth) -> dict:
        return {
            "final_response": (
                f"Resolved ticket {run.spec.trigger_id} for user "
                f"{auth.user_id}"
            ),
            "agents_used": ["support"],
        }

    runner = GraphJobRunner(invoker=_invoker)
    processor = AsyncioWorkerPoolProcessor()

    yield {
        "client": TestClient(app),
        "storage": storage,
        "queue": queue,
        "registry": registry,
        "resolver": resolver,
        "dispatcher": dispatcher,
        "runner": runner,
        "processor": processor,
    }

    await producer.stop()
    await conn.close()


# ── 1. High-priority happy path ─────────────────────────────


async def test_high_priority_ticket_triggers_run(helpdesk_app) -> None:
    """The webhook arrives, the signal is ingested, the trigger
    matches, and a SUCCEEDED JobRun lands with
    ``visibility='actor'`` AND ``visibility_user_id='u-test-1'`` —
    exactly the §26 default for ``act_as_user``."""
    client: TestClient = helpdesk_app["client"]

    payload = {
        "type": "support.ticket.created",
        "tenant_key": "helpdesk-demo",
        "user_id": "u-test-1",
        "occurred_at": "2026-05-06T09:00:00Z",
        "payload": {
            "ticket_id": "TKT-1",
            "priority": "high",
            "subject": "Cannot log in",
            "summary": "User locked out after password reset",
            "tags": ["auth", "lockout"],
        },
    }
    body = json.dumps(payload).encode()
    headers = {
        "x-orchid-source": "ticketing-system",
        "x-orchid-signature": _sign(body),
        "idempotency-key": "TKT-1:created:2026-05-06T09:00:00Z",
        "content-type": "application/json",
    }

    resp = client.post("/signals", content=body, headers=headers)
    assert resp.status_code == 202
    signal_id = resp.json()["signal_id"]
    assert signal_id

    await helpdesk_app["processor"].process_until_idle(
        queue=helpdesk_app["queue"],
        signal_store=helpdesk_app["storage"].signals,
        triggers=helpdesk_app["registry"],
        identity_resolver=helpdesk_app["resolver"],
        job_store=helpdesk_app["storage"].jobs,
        job_runner=helpdesk_app["runner"],
    )

    runs = await helpdesk_app["storage"].jobs.list()
    assert len(runs) == 1
    [run] = runs
    assert run.status == JobStatus.SUCCEEDED
    assert run.spec.trigger_id == "high-priority-ticket"
    assert run.spec.visibility == "actor"
    assert run.spec.visibility_user_id == "u-test-1"
    # The minted user-token threaded all the way through to the
    # invoker — provides a wire-level assertion that mint_for_user
    # was actually called instead of being silently bypassed.
    assert "u-test-1" in run.result.get("final_response", "")


# ── 2. Low-priority filtered by ``when:`` ───────────────────


async def test_low_priority_ticket_does_not_trigger(helpdesk_app) -> None:
    """A low-priority webhook is ingested (signal persists) but the
    ``when:`` filter excludes it, so the processor ack's the queue
    message without creating any :class:`JobRun`."""
    client: TestClient = helpdesk_app["client"]
    payload = {
        "type": "support.ticket.created",
        "tenant_key": "helpdesk-demo",
        "user_id": "u-test-1",
        "occurred_at": "2026-05-06T09:00:00Z",
        "payload": {"ticket_id": "TKT-2", "priority": "low", "subject": "x"},
    }
    body = json.dumps(payload).encode()
    headers = {
        "x-orchid-source": "ticketing-system",
        "x-orchid-signature": _sign(body),
        "idempotency-key": "TKT-2:low",
        "content-type": "application/json",
    }
    resp = client.post("/signals", content=body, headers=headers)
    assert resp.status_code == 202

    await helpdesk_app["processor"].process_until_idle(
        queue=helpdesk_app["queue"],
        signal_store=helpdesk_app["storage"].signals,
        triggers=helpdesk_app["registry"],
        identity_resolver=helpdesk_app["resolver"],
        job_store=helpdesk_app["storage"].jobs,
        job_runner=helpdesk_app["runner"],
    )

    # Signal persisted (audit trail), no JobRun created.
    signals = await helpdesk_app["storage"].signals.list()
    assert len(signals) == 1
    runs = await helpdesk_app["storage"].jobs.list()
    assert runs == []


# ── 3. Boot-time misconfiguration rejection ─────────────────


def test_act_as_user_trigger_rejected_when_resolver_lacks_minting() -> None:
    """A resolver that doesn't override :meth:`mint_for_user` raises
    :class:`MintingProbeUnsupportedError` at the registry's mint
    probe.  An ``act_as_user`` trigger pointed at such a resolver
    MUST fail at boot with a clear error naming both the trigger id
    and the resolver class — that's the §13 contract."""
    from orchid_ai.core.events.errors import TriggerRegistrationError
    from orchid_ai.core.identity import OrchidIdentityResolver

    class _BareResolver(OrchidIdentityResolver):
        async def resolve(self, domain, bearer):  # pragma: no cover
            from orchid_ai.core.state import OrchidAuthContext
            return OrchidAuthContext(access_token=bearer)

    bad_trigger = OrchidTriggerConfig(
        id="high-priority-ticket",
        on=OrchidTriggerMatchConfig(
            signal="support.ticket.created",
            when="payload.priority == 'high'",
        ),
        emits=OrchidTriggerEmitConfig(
            agent="support",
            prompt_template="x",
            identity=ActAsUserIdentity(user_id_from="signal.user_id"),
        ),
    )
    with pytest.raises(TriggerRegistrationError) as exc_info:
        build_registry_from_config(
            [bad_trigger],
            known_agents={"support"},
            identity_resolver=_BareResolver(),
        )
    msg = str(exc_info.value)
    assert "high-priority-ticket" in msg
    assert "_BareResolver" in msg


# ── Extra: HMAC signature mismatch ──────────────────────────


async def test_bad_signature_returns_401(helpdesk_app) -> None:
    """A webhook arriving with the wrong signature is rejected at
    the producer layer with 401 — no signal lands in the store, no
    JobRun is created."""
    client: TestClient = helpdesk_app["client"]
    body = json.dumps(
        {
            "type": "support.ticket.created",
            "tenant_key": "helpdesk-demo",
            "user_id": "u-test-1",
            "payload": {"priority": "high"},
        }
    ).encode()
    resp = client.post(
        "/signals",
        content=body,
        headers={
            "x-orchid-source": "ticketing-system",
            "x-orchid-signature": "sha256=" + ("0" * 64),  # wrong
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 401
    signals = await helpdesk_app["storage"].signals.list()
    assert signals == []
