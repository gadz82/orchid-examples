"""End-to-end test for external CLI delegation via the Orchid facade.

Exercises the full HITL flow:

- The orchestrator agent calls the ``ask_assistant`` external-agent tool.
- Because ``requires_approval`` defaults to ``True``, the graph interrupts.
- ``Orchid.invoke`` returns ``interrupted=True`` with pending approvals.
- ``Orchid.resume(approved=True)`` executes the subprocess and synthesises
  the final response.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.messages import ToolCall

from orchid_ai import Orchid, OrchidRuntime, load_config
from orchid_ai.checkpointing import build_checkpointer
from orchid_ai.config.schema import OrchidAgentsConfig
from orchid_ai.core.state import OrchidAuthContext

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory


_EXAMPLE_DIR = Path(__file__).resolve().parent.parent


def _build_hitl_config() -> OrchidAgentsConfig:
    """Load the example agents.yaml (already has ask_assistant)."""
    return load_config(str(_EXAMPLE_DIR / "agents.yaml"))


async def _make_orchid(
    factory: FakeChatModelFactory,
    tmp_root: Path,
) -> Orchid:
    """Build an Orchid client with the example config and deterministic LLM."""
    config = _build_hitl_config()
    chat_model = factory.build()
    checkpointer = await build_checkpointer(
        "sqlite",
        dsn=str(tmp_root / "checkpoints.db"),
    )
    runtime = OrchidRuntime(
        default_model="gemini/gemini-flash-latest",
        chat_model=chat_model,
        checkpointer=checkpointer,
    )
    return Orchid(config=config, runtime=runtime)


async def test_hitl_external_agent_delegation_and_resume(tmp_path: Path) -> None:
    """The orchestrator calls ask_assistant; after approval the subprocess runs."""
    factory = FakeChatModelFactory()
    # First turn: supervisor routes to orchestrator, orchestrator calls the tool.
    factory.add_structured_response(
        reasoning="Route to orchestrator for delegation",
        execution="parallel",
        agents=["orchestrator"],
    )
    factory.add_tool_calls(
        [ToolCall(name="ask_assistant", args={"prompt": "say hello"}, id="call_1")]
    )
    # Resume turn: supervisor routes back to orchestrator to synthesise the result.
    factory.add_structured_response(
        reasoning="Resume orchestrator after approval",
        execution="parallel",
        agents=["orchestrator"],
    )
    factory.add_text("The external assistant says: delegated response")

    chat_id = "hitl-chat-1"
    auth = OrchidAuthContext(access_token="", tenant_key="demo", user_id="u1")
    orchid = await _make_orchid(factory, tmp_path)
    try:
        result = await orchid.invoke(
            "Use the assistant to say hello",
            chat_id=chat_id,
            user_id="u1",
            tenant_id="demo",
            auth=auth,
            persist=False,
        )

        assert result.interrupted is True
        assert len(result.approvals_needed) == 1
        pending = result.approvals_needed[0]
        assert pending.tool == "ask_assistant"
        assert pending.agent == "orchestrator"
        assert pending.args.get("prompt") == "say hello"

        final = await orchid.resume(chat_id, auth=auth, approved=True, persist=False)
        assert final.interrupted is False
        assert "delegated response" in final.response.lower()
    finally:
        await orchid.close()
