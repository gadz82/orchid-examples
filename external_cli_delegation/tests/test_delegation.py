from __future__ import annotations

from pathlib import Path

import pytest

from orchid_ai.config.loader import load_config
from orchid_ai.config.tool_registry import TOOL_REGISTRY, clear


_EXAMPLE_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clean_registry():
    clear()
    yield
    clear()


class TestExternalCLIDelegationExample:
    def test_config_loads_external_agents(self):
        config = load_config(str(_EXAMPLE_DIR / "agents.yaml"))
        assert "ask_assistant" in config.external_agents

        agent_cfg = config.external_agents["ask_assistant"]
        assert agent_cfg.command == ["python", "-c"]
        assert agent_cfg.args == ["print('delegated response')"]
        assert agent_cfg.requires_approval is True
        assert agent_cfg.timeout == 30

    def test_orchestrator_references_external_tool(self):
        config = load_config(str(_EXAMPLE_DIR / "agents.yaml"))
        orchestrator = config.agents["orchestrator"]
        assert "ask_assistant" in orchestrator.tools

    def test_external_agent_defaults_applied(self):
        config = load_config(str(_EXAMPLE_DIR / "agents.yaml"))
        agent_cfg = config.external_agents["ask_assistant"]
        assert agent_cfg.stdin_mode == "arg"
        assert agent_cfg.normalizer == "passthrough"
        assert agent_cfg.cwd == ""
        assert agent_cfg.parallel_safe is False
        assert agent_cfg.inject_to_rag is False
        assert agent_cfg.rag_ttl is None
