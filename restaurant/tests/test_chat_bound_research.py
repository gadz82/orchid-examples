"""Phase-6 CI smoke test for ``examples/restaurant/`` — the
flagship §25 chat-binding scenario, extended with the Phase 4.5
in-chat live progress regression.

Three scenarios per ``.knowledge/pollen-bloom-examples.md`` §3 +
the Phase 4.5 §LS6/LS7 contract:

1. **Happy path**: a chat-time agent emits a signal with
   ``chat_id="self"``; the matched trigger has
   ``respect_chat_binding=true`` AND the resolved auth has write
   permission on the chat AND the chat exists; the Bloom's final
   ``AIMessage`` lands in that chat with ``metadata.origin="bloom"``.
2. **Cross-user smuggling rejection**: an attacker who controls user
   A pushes a hand-crafted signal with ``chat_binding`` pointing at
   user B's chat.  The signal is accepted (202) but the resulting
   :class:`JobRun` finishes ``status=FAILED`` with a
   :class:`ChatBindingForbiddenError`, and **nothing** is appended
   to user B's chat.

Both scenarios drive the events runtime + ``GraphJobRunner``
directly, with a tiny in-memory chat-storage stand-in.  No FastAPI,
no orchid-api lifespan — keeps the test fast and hermetic while
exercising the full §25.4 authorisation gate.
"""

from __future__ import annotations

import datetime as _dt
import uuid as _uuid
from pathlib import Path

import aiosqlite
import pytest

from examples.restaurant.identity import RestaurantIdentityResolver
from orchid_ai.config.schema_events import (
    ActAsUserIdentity,
    OrchidTriggerConfig,
    OrchidTriggerEmitConfig,
    OrchidTriggerMatchConfig,
)
from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.core.events.job import JobStatus
from orchid_ai.core.events.signal import SignalEnvelope
from orchid_ai.events.backends.sqlite import SQLiteEventStorage
from orchid_ai.events.processors.asyncio_pool import AsyncioWorkerPoolProcessor
from orchid_ai.events.queues.sqlite import SQLiteSignalQueue
from orchid_ai.events.registry import build_registry_from_config
from orchid_ai.events.runners.graph_runner import GraphJobRunner
from orchid_ai.events.streaming import BloomEventStream, ChatBloomEvent
from orchid_ai.persistence.models import OrchidChatSession


# ── Tiny in-memory chat-storage stand-in ────────────────────


class _InMemoryChatStorage:
    """Minimum surface the runner's ``_resolve_chat_binding`` calls.

    Real ``OrchidChatStorage`` implementations come from
    :mod:`orchid_ai.persistence` and aren't needed for this test —
    we only exercise the §25 binding contract.
    """

    def __init__(self) -> None:
        self._chats: dict[str, OrchidChatSession] = {}
        self.messages: list[dict] = []

    def add_chat(
        self, chat_id: str, *, owner: str, tenant: str = "restaurant-demo"
    ) -> None:
        now = _dt.datetime.now(tz=_dt.UTC)
        self._chats[chat_id] = OrchidChatSession(
            id=chat_id,
            tenant_id=tenant,
            user_id=owner,
            title="x",
            created_at=now,
            updated_at=now,
        )

    async def get_chat_metadata(self, chat_id: str):
        return self._chats.get(chat_id)

    async def can_write(self, chat: OrchidChatSession, auth) -> bool:
        if chat.tenant_id != auth.tenant_key:
            return False
        if chat.user_id == auth.user_id:
            return True
        return "admin" in (auth.roles or frozenset())

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        agents_used: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        record = {
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "agents_used": list(agents_used or []),
            "metadata": dict(metadata or {}),
        }
        self.messages.append(record)
        return record


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
async def restaurant_app(tmp_path: Path):
    """Bring up the events runtime + a chat-storage stand-in for the
    :class:`GraphJobRunner` to write into."""
    dsn = str(tmp_path / "restaurant-events.db")
    conn = await aiosqlite.connect(dsn)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    storage = SQLiteEventStorage(conn=conn)
    await storage.init_db()
    queue = SQLiteSignalQueue(conn=conn)

    trigger = OrchidTriggerConfig(
        id="deep-research",
        on=OrchidTriggerMatchConfig(signal="research.requested"),
        emits=OrchidTriggerEmitConfig(
            agent="reviews",
            prompt_template="Carry out deep research: {{payload.question}}",
            identity=ActAsUserIdentity(user_id_from="signal.user_id"),
            respect_chat_binding=True,
        ),
    )
    resolver = RestaurantIdentityResolver()
    resolver.seed("u-alice", token="t:u-alice")
    resolver.seed("u-bob", token="t:u-bob")
    registry = build_registry_from_config(
        [trigger], known_agents={"reviews"}, identity_resolver=resolver
    )
    dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)

    chat_storage = _InMemoryChatStorage()

    async def _research_invoker(run, auth) -> dict:
        return {
            "final_response": (
                f"Deep-research result for {auth.user_id}: "
                f"{run.spec.prompt[:80]}..."
            ),
            "agents_used": ["reviews"],
        }

    runner = GraphJobRunner(invoker=_research_invoker, chat_storage=chat_storage)
    processor = AsyncioWorkerPoolProcessor()

    yield {
        "storage": storage,
        "queue": queue,
        "registry": registry,
        "resolver": resolver,
        "dispatcher": dispatcher,
        "runner": runner,
        "processor": processor,
        "chat_storage": chat_storage,
    }
    await conn.close()


# ── 1. Happy path: chat-bound Bloom lands in chat ───────────


async def test_chat_bound_research_lands_in_chat(restaurant_app) -> None:
    """User Alice's concierge agent emits a signal with
    ``chat_id="self"`` pointing at her chat.  The Bloom runs as
    Alice (mint_for_user → Alice's token), the runner appends the
    final ``AIMessage`` to Alice's chat with the bloom origin
    badge."""
    chat_id = "C-alice-1"
    restaurant_app["chat_storage"].add_chat(chat_id, owner="u-alice")

    envelope = SignalEnvelope(
        type="research.requested",
        payload={
            "question": "Plan a 4-day food itinerary in Bologna, budget €400.",
        },
        source="internal:agent:concierge",
        occurred_at=_dt.datetime.now(tz=_dt.UTC),
        tenant_key="restaurant-demo",
        user_id="u-alice",
        identity_claim={
            "mode": "act_as_user",
            "user_id_from": "signal.user_id",
        },
        chat_binding={
            "chat_id": chat_id,
            "mode": "append_final_message",
            "on_failure": "post_error",
        },
        dedupe_key=f"research:{chat_id}:bologna",
    )
    await restaurant_app["dispatcher"].ingest(envelope)

    await restaurant_app["processor"].process_until_idle(
        queue=restaurant_app["queue"],
        signal_store=restaurant_app["storage"].signals,
        triggers=restaurant_app["registry"],
        identity_resolver=restaurant_app["resolver"],
        job_store=restaurant_app["storage"].jobs,
        job_runner=restaurant_app["runner"],
    )

    runs = await restaurant_app["storage"].jobs.list()
    assert len(runs) == 1
    [run] = runs
    assert run.status == JobStatus.SUCCEEDED
    assert run.spec.visibility == "actor"
    assert run.spec.visibility_user_id == "u-alice"
    # The bound chat now has exactly one bloom-origin message.
    msgs = restaurant_app["chat_storage"].messages
    assert len(msgs) == 1
    assert msgs[0]["chat_id"] == chat_id
    assert msgs[0]["metadata"]["origin"] == "bloom"
    assert msgs[0]["metadata"]["bloom_run_id"] == str(run.run_id)
    assert msgs[0]["metadata"]["trigger_id"] == "deep-research"
    assert "deep-research result for u-alice" in msgs[0]["content"].lower()


# ── 2. Cross-user smuggling rejection ───────────────────────


async def test_signal_targeting_another_users_chat_is_rejected(
    restaurant_app,
) -> None:
    """An attacker who controls user A pushes a hand-crafted signal
    whose ``chat_binding`` points at user B's chat.  Even though
    the dispatcher accepts the signal (it's well-formed) the
    runner's ``_resolve_chat_binding`` MUST reject the binding at
    the §25.4 authorisation gate: the auth resolved by
    ``mint_for_user`` is user A, not the chat's owner B.

    Expected outcome:

    - Signal persists (audit trail).
    - :class:`JobRun` finishes ``status=FAILED`` with
      :class:`ChatBindingForbiddenError`.
    - Per §25.4, **nothing** is appended to user B's chat — the
      ``on_failure`` post is suppressed when the binding lookup
      itself failed.
    """
    chat_b = "C-bob-1"
    restaurant_app["chat_storage"].add_chat(chat_b, owner="u-bob")

    # User A pushes the smuggling signal.
    envelope = SignalEnvelope(
        type="research.requested",
        payload={"question": "leak"},
        source="api:public",
        occurred_at=_dt.datetime.now(tz=_dt.UTC),
        tenant_key="restaurant-demo",
        user_id="u-alice",  # ← signal claims A; mint_for_user → A
        identity_claim={
            "mode": "act_as_user",
            "user_id_from": "signal.user_id",
        },
        chat_binding={
            "chat_id": chat_b,  # ← attempting to write to B's chat
            "mode": "append_final_message",
            "on_failure": "silent",
        },
        dedupe_key=f"smuggle:{_uuid.uuid4()}",
    )
    await restaurant_app["dispatcher"].ingest(envelope)

    await restaurant_app["processor"].process_until_idle(
        queue=restaurant_app["queue"],
        signal_store=restaurant_app["storage"].signals,
        triggers=restaurant_app["registry"],
        identity_resolver=restaurant_app["resolver"],
        job_store=restaurant_app["storage"].jobs,
        job_runner=restaurant_app["runner"],
    )

    [run] = await restaurant_app["storage"].jobs.list()
    assert run.status == JobStatus.FAILED
    assert "Forbidden" in (run.error or "")
    # Bob's chat is untouched — no appended messages.
    assert restaurant_app["chat_storage"].messages == []


# ── 3. Chat-binding ignored when trigger doesn't opt in ─────


async def test_chat_binding_ignored_when_trigger_does_not_opt_in(
    tmp_path: Path,
) -> None:
    """A trigger without ``respect_chat_binding=true`` MUST drop the
    binding silently — even if the signal carries one.  This is the
    §25.2 contract: chat binding is opt-in, never opt-out."""
    dsn = str(tmp_path / "no-opt-in.db")
    conn = await aiosqlite.connect(dsn)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    storage = SQLiteEventStorage(conn=conn)
    await storage.init_db()
    queue = SQLiteSignalQueue(conn=conn)
    try:
        # Same trigger but WITHOUT respect_chat_binding=true.
        trigger = OrchidTriggerConfig(
            id="deep-research",
            on=OrchidTriggerMatchConfig(signal="research.requested"),
            emits=OrchidTriggerEmitConfig(
                agent="reviews",
                prompt_template="x",
                identity=ActAsUserIdentity(user_id_from="signal.user_id"),
                # NOTE: no respect_chat_binding → defaults to False
            ),
        )
        resolver = RestaurantIdentityResolver()
        resolver.seed("u-alice", token="t:u-alice")
        registry = build_registry_from_config(
            [trigger], known_agents={"reviews"}, identity_resolver=resolver
        )
        dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)
        chat_storage = _InMemoryChatStorage()
        chat_storage.add_chat("C-1", owner="u-alice")

        async def _ok(run, auth) -> dict:
            return {"final_response": "ok"}

        runner = GraphJobRunner(invoker=_ok, chat_storage=chat_storage)
        processor = AsyncioWorkerPoolProcessor()

        await dispatcher.ingest(
            SignalEnvelope(
                type="research.requested",
                payload={},
                source="src",
                occurred_at=_dt.datetime.now(tz=_dt.UTC),
                tenant_key="restaurant-demo",
                user_id="u-alice",
                identity_claim={
                    "mode": "act_as_user",
                    "user_id_from": "signal.user_id",
                },
                chat_binding={"chat_id": "C-1"},
            )
        )
        await processor.process_until_idle(
            queue=queue,
            signal_store=storage.signals,
            triggers=registry,
            identity_resolver=resolver,
            job_store=storage.jobs,
            job_runner=runner,
        )

        [run] = await storage.jobs.list()
        assert run.status == JobStatus.SUCCEEDED
        # Trigger didn't opt in → binding stripped at build_job_spec.
        assert run.spec.chat_binding is None
        # Nothing appended to the chat.
        assert chat_storage.messages == []
    finally:
        await conn.close()


# ── 4. Phase 4.5: chat-bound run emits progress to the chat channel ──


async def test_chat_bound_research_emits_progress_to_chat(
    restaurant_app,
) -> None:
    """The Phase 4.5 §LS6/LS7 regression: a chat-bound Bloom MUST
    emit ``chat.bloom.attached`` → ``chat.bloom.tick``-or-not →
    ``chat.bloom.finished`` on the chat channel while the run is in
    flight, with anchoring metadata (``source_message_id`` +
    ``trigger_id``) carried through.

    Drives the dispatcher → processor pipeline directly with a
    :class:`BloomEventStream` injected on the processor; subscribes
    to ``chat:{chat_id}`` BEFORE running the processor so we capture
    every published event.  The ``result`` is NOT carried on
    ``chat.bloom.finished`` (LS2) — the final ``AIMessage`` flows
    through chat storage instead, and we re-assert the §25.5
    contract here as belt-and-braces.
    """
    chat_id = "C-alice-progress"
    restaurant_app["chat_storage"].add_chat(chat_id, owner="u-alice")

    # The fixture's processor doesn't have an event stream by
    # default; the API lifespan would normally wire it.  We pass
    # the stream explicitly to ``process_until_idle`` below so the
    # dual-publish branch fires.
    stream = BloomEventStream(idle_timeout_seconds=1.0)

    # Subscribe to the chat channel BEFORE ingesting so no events
    # are missed.  The subscription returns when the terminal event
    # arrives.
    received: list[ChatBloomEvent] = []
    import asyncio as _asyncio

    async def _consume() -> None:
        async for evt in stream.subscribe(f"chat:{chat_id}"):
            received.append(evt)
            if evt.is_terminal():
                return

    task = _asyncio.create_task(_consume())
    # Give the subscriber a tick to register on the channel.
    await _asyncio.sleep(0)

    envelope = SignalEnvelope(
        type="research.requested",
        payload={
            "question": "Plan a 4-day food itinerary in Bologna, budget €400.",
        },
        source="internal:agent:concierge",
        occurred_at=_dt.datetime.now(tz=_dt.UTC),
        tenant_key="restaurant-demo",
        user_id="u-alice",
        identity_claim={
            "mode": "act_as_user",
            "user_id_from": "signal.user_id",
        },
        chat_binding={
            "chat_id": chat_id,
            "mode": "append_final_message",
            "on_failure": "post_error",
            "source_message_id": "m-anchor",
        },
        dedupe_key=f"progress:{chat_id}:{_uuid.uuid4()}",
    )
    await restaurant_app["dispatcher"].ingest(envelope)

    await restaurant_app["processor"].process_until_idle(
        queue=restaurant_app["queue"],
        signal_store=restaurant_app["storage"].signals,
        triggers=restaurant_app["registry"],
        identity_resolver=restaurant_app["resolver"],
        job_store=restaurant_app["storage"].jobs,
        job_runner=restaurant_app["runner"],
        event_stream=stream,
    )
    await _asyncio.wait_for(task, timeout=2.0)

    types = [e.type for e in received]
    # ``queued`` and ``started`` collapse into TWO ``attached`` events
    # (LS8 — the frontend dedupes by run_id).  Then a single
    # ``finished``.
    assert types[0] == "chat.bloom.attached"
    assert types[-1] == "chat.bloom.finished"
    assert types.count("chat.bloom.attached") == 2
    # Anchoring metadata is forwarded to every event.
    assert all(e.payload.get("source_message_id") == "m-anchor" for e in received)
    assert all(e.payload.get("trigger_id") == "deep-research" for e in received)
    assert all(e.payload.get("identity_mode") == "act_as_user" for e in received)
    # ``result`` is NOT carried on chat.bloom.finished (LS2).
    finished_payload = received[-1].payload
    assert finished_payload["status"] == "succeeded"
    assert "result" not in finished_payload

    # Belt-and-braces: the §25.5 final-message persistence contract
    # also holds — chat storage carries the bloom-origin message.
    msgs = restaurant_app["chat_storage"].messages
    assert len(msgs) == 1
    assert msgs[0]["metadata"]["origin"] == "bloom"
