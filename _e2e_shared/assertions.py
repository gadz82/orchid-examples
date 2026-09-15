"""Domain-specific assertion helpers for e2e tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from orchid_ai.core.state import OrchidAuthContext
from orchid_ai.events.visibility import run_is_visible

if TYPE_CHECKING:
    from orchid_ai.core.events.job import JobRun


def assert_agent_routed(response: dict[str, Any], expected_agent: str) -> None:
    """Assert that the response indicates the expected agent was used.

    Looks for ``agents_used`` list or an ``agent`` field.
    """
    agents_used = response.get("agents_used") or []
    if expected_agent in agents_used:
        return
    agent_field = response.get("agent") or response.get("agent_name")
    if agent_field == expected_agent:
        return
    raise AssertionError(
        f"Expected agent {expected_agent!r} in response, got agents_used={agents_used!r}, "
        f"agent={agent_field!r}"
    )


def assert_rag_context_present(response: dict[str, Any], expected_terms: list[str]) -> None:
    """Assert that the response mentions one of the expected RAG terms."""
    text = _response_text(response).lower()
    missing = [term for term in expected_terms if term.lower() not in text]
    if missing:
        raise AssertionError(
            f"Expected response to contain RAG terms {missing!r}, full text: {text!r}"
        )


def assert_guardrail_applied(response: dict[str, Any], guardrail_type: str) -> None:
    """Assert that a guardrail was triggered.

    ``guardrail_type`` is ``"input"`` or ``"output"``.
    """
    text = _response_text(response).lower()
    if guardrail_type == "input":
        keywords = ("blocked", "cannot", "inappropriate", "input")
    else:
        keywords = ("redacted", "removed", "cannot share", "sensitive")
    if not any(k in text for k in keywords):
        raise AssertionError(
            f"Expected {guardrail_type} guardrail signal in response, got: {text!r}"
        )


def assert_tool_called(response: dict[str, Any], tool_name: str) -> None:
    """Assert that the response indicates the tool was called."""
    text = _response_text(response).lower()
    tools_used = response.get("tools_used") or []
    if tool_name in tools_used:
        return
    if tool_name.lower() in text:
        return
    raise AssertionError(
        f"Expected tool {tool_name!r} to be called, got tools_used={tools_used!r}, text={text!r}"
    )


def assert_visibility_boundary(
    run: JobRun,
    auth: OrchidAuthContext,
    expected_visible: bool,
) -> None:
    """Assert the visibility boundary for a JobRun."""
    visible = run_is_visible(run, auth)
    if visible != expected_visible:
        raise AssertionError(
            f"Expected run visible={expected_visible} for auth {auth}, got {visible}. "
            f"Run visibility={run.spec.visibility!r}, user={run.spec.visibility_user_id!r}"
        )


def assert_successful_response(response: dict[str, Any]) -> None:
    """Assert that an orchid-api response is successful."""
    if response.get("error"):
        raise AssertionError(f"Expected successful response, got error: {response['error']}")


def _response_text(response: dict[str, Any]) -> str:
    """Extract text from various response shapes."""
    if isinstance(response, str):
        return response
    if "final_response" in response:
        return str(response["final_response"])
    if "content" in response:
        return str(response["content"])
    if "message" in response:
        return str(response["message"])
    return str(response)
