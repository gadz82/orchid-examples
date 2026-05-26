from __future__ import annotations

import datetime as _dt
import uuid as _uuid

import pytest

from examples.education.identity import EducationIdentityResolver
from orchid_ai.core.events.job import JobStatus
from orchid_ai.core.events.signal import SignalEnvelope
from orchid_ai.core.events.store import OrchidScheduleRecord
from orchid_ai.core.state import OrchidAuthContext
from orchid_ai.events.visibility import run_is_visible


@pytest.mark.asyncio
async def test_weekly_quiz_visible_to_same_tenant_users(tmp_path, education_events, build_event_runtime) -> None:
    resolver = EducationIdentityResolver()

    async def _invoker(run, auth) -> dict:
        return {"final_response": f"Weekly digest by {auth.extra.get('service_account', '')}"}

    runtime = await build_event_runtime(
        tmp_path,
        trigger_ids=["weekly-quiz"],
        resolver=resolver,
        invoker=_invoker,
        db_name="education-visibility-scheduled.db",
    )
    try:
        schedule = next(schedule for schedule in education_events.schedules if schedule.id == "weekly-quiz-cron")
        await runtime["storage"].schedules.upsert(
            OrchidScheduleRecord(
                schedule_id=schedule.id,
                trigger_id=schedule.trigger_id,
                cron=schedule.cron,
                interval_seconds=schedule.interval_seconds,
                identity_claim=schedule.identity.model_dump(),
                last_fire_at=None,
                next_fire_at=None,
                enabled=schedule.enabled,
            )
        )

        fire_iso = "2026-05-25T08:00:00+00:00"
        await runtime["dispatcher"].ingest(
            SignalEnvelope(
                type="cron",
                payload={"schedule_id": schedule.id, "fire_time": fire_iso},
                source=f"scheduler:{schedule.id}",
                occurred_at=_dt.datetime.fromisoformat(fire_iso),
                tenant_key="education-demo",
                identity_claim={"mode": "service_account", "name": "quiz-bot"},
                dedupe_key=f"{schedule.id}:{fire_iso}",
            )
        )

        await runtime["processor"].process_until_idle(
            queue=runtime["queue"],
            signal_store=runtime["storage"].signals,
            triggers=runtime["registry"],
            identity_resolver=resolver,
            job_store=runtime["storage"].jobs,
            job_runner=runtime["runner"],
        )

        [run] = await runtime["storage"].jobs.list()
        assert run.status == JobStatus.SUCCEEDED

        same_tenant_user = OrchidAuthContext(
            access_token="tok",
            tenant_key="education-demo",
            user_id="u-peer",
        )
        assert run_is_visible(run, same_tenant_user) is True
    finally:
        await runtime["close"]()


@pytest.mark.asyncio
async def test_chat_bound_run_visible_only_to_actor(
    tmp_path,
    build_event_runtime,
    chat_storage_factory,
    sample_text: str,
) -> None:
    resolver = EducationIdentityResolver()
    resolver.seed("u-student-1", token="tok:u-student-1")
    chat_storage = chat_storage_factory()
    chat_storage.add_chat("C-education-visibility", owner="u-student-1")

    async def _invoker(run, auth) -> dict:
        return {"final_response": f"Summary for {auth.user_id}: {run.spec.prompt[:60]}"}

    runtime = await build_event_runtime(
        tmp_path,
        trigger_ids=["chat-bound-generation"],
        resolver=resolver,
        invoker=_invoker,
        chat_storage=chat_storage,
        db_name="education-visibility-chat.db",
    )
    try:
        await runtime["dispatcher"].ingest(
            SignalEnvelope(
                type="education.generate",
                payload={"source_text": sample_text},
                source="internal:agent:education-studio",
                occurred_at=_dt.datetime.now(tz=_dt.UTC),
                tenant_key="education-demo",
                user_id="u-student-1",
                identity_claim={"mode": "act_as_user", "user_id_from": "signal.user_id"},
                chat_binding={"chat_id": "C-education-visibility"},
                dedupe_key=f"chat:{_uuid.uuid4()}",
            )
        )

        await runtime["processor"].process_until_idle(
            queue=runtime["queue"],
            signal_store=runtime["storage"].signals,
            triggers=runtime["registry"],
            identity_resolver=resolver,
            job_store=runtime["storage"].jobs,
            job_runner=runtime["runner"],
        )

        [run] = await runtime["storage"].jobs.list()
        assert run.status == JobStatus.SUCCEEDED
        assert run.spec.visibility == "actor"

        actor = OrchidAuthContext(
            access_token="tok",
            tenant_key="education-demo",
            user_id="u-student-1",
        )
        peer = OrchidAuthContext(
            access_token="tok",
            tenant_key="education-demo",
            user_id="u-student-2",
        )
        assert run_is_visible(run, actor) is True
        assert run_is_visible(run, peer) is False
    finally:
        await runtime["close"]()
