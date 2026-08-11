"""Tests for MCP server configuration in agents.yaml."""

from __future__ import annotations

import pytest
import yaml
from orchid_ai.config.loader import load_config


class TestMCPConfig:
    """Cover MCP server auth modes and tool allowlists."""

    @pytest.fixture
    def config(self):
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
        return load_config(str(path))

    def test_slack_server_present_with_send_only_tools(self, config) -> None:
        slack_servers = []
        for agent in config.agents.values():
            for server in agent.mcp_servers:
                if server.name == "slack":
                    slack_servers.append(server)

        assert slack_servers, "Slack MCP server not found in any agent"
        for server in slack_servers:
            tool_names = {t.name for t in server.tools}
            assert tool_names == {"chat_postMessage", "chat_postEphemeral"}
            for tool in server.tools:
                assert tool.inject_to_rag is False
            assert server.auth.mode == "passthrough"

    def test_datadog_is_passthrough_with_read_tools(self, config) -> None:
        datadog_servers = []
        for agent in config.agents.values():
            for server in agent.mcp_servers:
                if server.name == "datadog":
                    datadog_servers.append(server)

        assert datadog_servers, "Datadog MCP server not found"
        for server in datadog_servers:
            assert server.auth.mode == "passthrough"
            for tool in server.tools:
                assert tool.inject_to_rag is True
            tool_names = {t.name for t in server.tools}
            assert "query_logs" in tool_names
            assert "query_metrics" in tool_names

    def test_atlassian_read_tools_have_inject_to_rag(self, config) -> None:
        for agent in config.agents.values():
            for server in agent.mcp_servers:
                if server.name != "atlassian-rovo":
                    continue
                read_tools = {t.name for t in server.tools if t.inject_to_rag}
                assert "getConfluencePage" in read_tools
                assert "searchConfluenceUsingCql" in read_tools

    def test_static_agents_exclude_dynamic(self, config) -> None:
        static_agents = [
            "notification-expert",
            "mailer-expert",
            "push-expert",
            "eventbus-expert",
            "domains-expert",
            "devops-expert",
            "messenger-expert",
            "standards-coach",
        ]
        for name in static_agents:
            agent = config.agents.get(name)
            assert agent is not None, f"Agent {name} not found"
            assert agent.rag.retrieval.exclude_dynamic is True, f"{name} missing exclude_dynamic"

    def test_live_agents_do_not_exclude_dynamic(self, config) -> None:
        live_agents = ["sre-investigator", "delivery-analyst"]
        for name in live_agents:
            agent = config.agents.get(name)
            assert agent is not None, f"Agent {name} not found"
            assert agent.rag.retrieval.exclude_dynamic is False, f"{name} should not exclude dynamic"

    def test_yaml_loads_without_error(self) -> None:
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
        with open(path) as f:
            data = yaml.safe_load(f)
        assert "agents" in data
        assert "slack" in {s["name"] for agent in data["agents"].values() for s in agent.get("mcp_servers", [])}
