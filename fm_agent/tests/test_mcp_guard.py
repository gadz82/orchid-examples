"""Tests for MCP tool allowlist guard."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from orchid_ai.config.schema_mcp import OrchidMCPServerConfig
from orchid_ai.core.mcp import OrchidMCPClient
from orchid_ai.core.state import OrchidAuthContext

from examples.fm_agent.hooks.mcp_guard import enforce_atlassian_allowlist


class TestMCPGuard:
    """Cover advertised-vs-allowlist diff behavior."""

    @pytest.fixture
    def server_config(self):
        return OrchidMCPServerConfig(
            name="atlassian-rovo",
            type="remote",
            url="https://mcp.atlassian.com/v1/mcp",
            tools=[
                {"name": "getConfluencePage", "inject_to_rag": True},
                {"name": "searchConfluenceUsingCql", "inject_to_rag": True},
            ],
        )

    @pytest.fixture
    def auth(self):
        return OrchidAuthContext(access_token="token")

    async def test_returns_empty_when_all_tools_allowlisted(self, server_config, auth) -> None:
        client = AsyncMock(spec=OrchidMCPClient)
        client.list_tools = AsyncMock(return_value=[
            {"name": "getConfluencePage"},
            {"name": "searchConfluenceUsingCql"},
        ])

        unpinned = await enforce_atlassian_allowlist(server_config, client, auth)

        assert unpinned == []
        client.list_tools.assert_awaited_once_with(auth)

    async def test_logs_unpinned_tools(self, server_config, auth, caplog) -> None:
        client = AsyncMock(spec=OrchidMCPClient)
        client.list_tools = AsyncMock(return_value=[
            {"name": "getConfluencePage"},
            {"name": "dangerousWriteTool"},
            {"name": "searchConfluenceUsingCql"},
        ])

        unpinned = await enforce_atlassian_allowlist(server_config, client, auth)

        assert unpinned == ["dangerousWriteTool"]
        assert "dangerousWriteTool" in caplog.text

    async def test_fail_open_on_list_error(self, server_config, auth, caplog) -> None:
        client = AsyncMock(spec=OrchidMCPClient)
        client.list_tools = AsyncMock(side_effect=RuntimeError("connection refused"))

        unpinned = await enforce_atlassian_allowlist(server_config, client, auth)

        assert unpinned == []
        assert "Could not list tools" in caplog.text

    async def test_handles_object_style_tools(self, server_config, auth) -> None:
        class Tool:
            name = "extraTool"

        client = AsyncMock(spec=OrchidMCPClient)
        client.list_tools = AsyncMock(return_value=[Tool()])

        unpinned = await enforce_atlassian_allowlist(server_config, client, auth)

        assert unpinned == ["extraTool"]
