"""Offline tests for the smart intake router example."""

from __future__ import annotations

import asyncio
from pathlib import Path

from langchain_core.messages import HumanMessage

from orchid_ai.agents.generic_agent import GenericAgent
from orchid_ai.config.loader import load_config
from orchid_ai.decision.factory import build_decision_models
from orchid_ai.graph.routing import build_routing_strategy
from orchid_ai.rag.backends.null import NullVectorReader
from orchid_ai.runtime import OrchidRuntime

CONFIG = Path(__file__).parents[1] / "config" / "agents.yaml"
ROUTER_ANSWER = "I was charged twice for the same invoice"
SKILL_ANSWER = "Please refund the duplicate charge"


def _config():
    return load_config(str(CONFIG))


def _runtime(config):
    return OrchidRuntime(default_model="ollama/llama3.2", decision_models=build_decision_models(config))


def _state(text: str) -> dict:
    return {"messages": [HumanMessage(content=text)]}


def test_stub_config_loads() -> None:
    config = _config()
    assert config.decision_models["router"].protocol == "stub"
    assert set(config.agents) == {"billing", "technical", "account", "general"}


def test_routing_selects_billing() -> None:
    config = _config()
    strategy = build_routing_strategy(config, _runtime(config))
    assert strategy is not None
    decision = asyncio.run(
        strategy.route(
            state=_state(ROUTER_ANSWER),
            agent_descriptions={name: agent.description for name, agent in config.agents.items()},
            orchestrator_skills=config.skills,
        )
    )
    assert decision is not None
    assert decision.agents == ["billing"]
    assert decision.execution == "parallel"


def test_routing_selects_the_refund_skill() -> None:
    config = _config()
    strategy = build_routing_strategy(config, _runtime(config))
    assert strategy is not None
    decision = asyncio.run(
        strategy.route(
            state=_state(SKILL_ANSWER),
            agent_descriptions={name: agent.description for name, agent in config.agents.items()},
            orchestrator_skills=config.skills,
        )
    )
    assert decision is not None
    assert decision.execution == "skill"
    assert decision.skill == "refund_request"


def test_tool_shortlist_selects_the_invoice_tool() -> None:
    config = _config()
    runtime = _runtime(config)
    agent = GenericAgent(
        config=config.agents["billing"],
        reader=NullVectorReader(),
        tool_decision_model=runtime.get_decision_model("router"),
    )
    tools = [
        {"type": "function", "function": {"name": "lookup_invoice", "description": "Invoice lookup"}},
        {"type": "function", "function": {"name": "send_email", "description": "Send an email"}},
    ]
    selected = asyncio.run(agent._shortlist_tools(ROUTER_ANSWER, tools))
    assert selected == ["lookup_invoice"]
