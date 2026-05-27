from __future__ import annotations

import datetime as _dt
import uuid as _uuid

import pytest

from examples.education.identity import EducationIdentityResolver
from orchid_ai.core.events.job import JobStatus
from orchid_ai.core.events.signal import SignalEnvelope


@pytest.mark.asyncio
async def test_chat_emit_signal_for_generation(
    tmp_path,
    build_event_runtime,
    chat_storage_factory,
    sample_text: str,
) -> None:
    resolver = EducationIdentityResolver()
    resolver.seed("u-student-1", token="tok:u-student-1")
    chat_storage = chat_storage_factory()
    chat_storage.add_chat("C-education-1", owner="u-student-1")

    async def _invoker(run, auth) -> dict:
        source_line = next((line.strip() for line in run.spec.prompt.splitlines() if line.strip().startswith("#")), "")
        return {
            "final_response": (
                f"Study summary for {auth.user_id}: "
                f"{source_line}"
            ),
            "agents_used": ["content-analyzer"],
        }

    runtime = await build_event_runtime(
        tmp_path,
        trigger_ids=["chat-bound-generation"],
        resolver=resolver,
        invoker=_invoker,
        chat_storage=chat_storage,
        db_name="education-chat-bound.db",
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
                chat_binding={
                    "chat_id": "C-education-1",
                    "mode": "append_final_message",
                    "on_failure": "post_error",
                },
                dedupe_key=f"education:{_uuid.uuid4()}",
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

        runs = await runtime["storage"].jobs.list()
        assert len(runs) == 1
        [run] = runs
        assert run.status == JobStatus.SUCCEEDED
        assert run.spec.trigger_id == "chat-bound-generation"
        assert run.spec.visibility == "actor"
        assert run.spec.visibility_user_id == "u-student-1"

        messages = chat_storage.messages
        assert len(messages) == 1
        assert messages[0]["chat_id"] == "C-education-1"
        assert messages[0]["metadata"]["origin"] == "bloom"
        assert messages[0]["metadata"]["trigger_id"] == "chat-bound-generation"
        assert messages[0]["metadata"]["bloom_run_id"] == str(run.run_id)
        assert "u-student-1" in messages[0]["content"]
        assert "Photosynthesis" in messages[0]["content"]
    finally:
        await runtime["close"]()
