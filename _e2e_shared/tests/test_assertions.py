"""Self-tests for assertion helpers."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

import pytest
from examples._e2e_shared.assertions import (
    assert_agent_routed,
    assert_guardrail_applied,
    assert_rag_context_present,
    assert_successful_response,
    assert_tool_called,
    assert_visibility_boundary,
)
from examples._e2e_shared.fixtures.auth import make_auth_context
from orchid_ai.core.events.job import JobRun, JobSpec, JobStatus


def test_assert_agent_routed_with_agents_used() -> None:
    assert_agent_routed({"agents_used": ["basketball", "psychologist"]}, "basketball")


def test_assert_agent_routed_with_agent_field() -> None:
    assert_agent_routed({"agent": "basketball"}, "basketball")


def test_assert_agent_routed_fails_when_missing() -> None:
    with pytest.raises(AssertionError):
        assert_agent_routed({"agents_used": ["psychologist"]}, "basketball")


def test_assert_rag_context_present() -> None:
    assert_rag_context_present({"final_response": "The menu has pasta."}, ["pasta"])


def test_assert_rag_context_present_fails_when_missing() -> None:
    with pytest.raises(AssertionError):
        assert_rag_context_present({"final_response": "hello"}, ["pasta"])


def test_assert_guardrail_applied_input() -> None:
    assert_guardrail_applied({"final_response": "That input is inappropriate."}, "input")


def test_assert_guardrail_applied_output() -> None:
    assert_guardrail_applied({"final_response": "Sensitive data redacted."}, "output")


def test_assert_tool_called_by_name() -> None:
    assert_tool_called({"tools_used": ["search"]}, "search")


def test_assert_tool_called_in_text() -> None:
    assert_tool_called({"final_response": "I called search for you."}, "search")


def test_assert_successful_response() -> None:
    assert_successful_response({"final_response": "ok"})


def test_assert_successful_response_fails_on_error() -> None:
    with pytest.raises(AssertionError):
        assert_successful_response({"error": "boom"})


def _make_run(visibility: str, visibility_user_id: str | None = None) -> JobRun:
    return JobRun(
        run_id=_uuid.uuid4(),
        spec=JobSpec(
            trigger_id="t1",
            signal_id=_uuid.uuid4(),
            agent_name="a1",
            prompt="x",
            identity_claim={},
            correlation_id=None,
            parallelism_key="t1:u1",
            visibility=visibility,
            visibility_user_id=visibility_user_id,
        ),
        attempt_number=1,
        status=JobStatus.SUCCEEDED,
        queued_at=datetime.now(timezone.utc),
    )


def test_assert_visibility_boundary() -> None:
    run = _make_run("actor", visibility_user_id="u1")
    assert_visibility_boundary(run, make_auth_context(user_id="u1"), expected_visible=True)
    assert_visibility_boundary(run, make_auth_context(user_id="u2"), expected_visible=False)
