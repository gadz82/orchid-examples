"""Mock MCP clients and servers for hermetic e2e tests."""

from __future__ import annotations

from typing import Any

import pytest
from orchid_ai.core.mcp import OrchidCacheableMCPClient, OrchidMCPClient
from orchid_ai.core.mcp_result import OrchidMCPToolResult
from orchid_ai.core.state import OrchidAuthContext


class MockMCPClient(OrchidMCPClient):
    """Configurable MCP client for tests.

    Supports tool-call mocking, capability discovery, and cache warming.
    """

    def __init__(
        self,
        *,
        url: str = "http://localhost/mcp",
        tools: list[dict[str, Any]] | None = None,
        responses: dict[str, Any] | None = None,
        default_response: Any = None,
    ) -> None:
        self._url = url
        self._tools = tools or []
        self._responses = responses or {}
        self._default_response = default_response
        self._calls: list[tuple[str, dict[str, Any]]] = []

    @property
    def server_url(self) -> str:
        return self._url

    def add_tool(
        self,
        name: str,
        description: str = "",
        input_schema: dict[str, Any] | None = None,
    ) -> MockMCPClient:
        """Register a tool in the discovery list."""
        self._tools.append(
            {
                "name": name,
                "description": description,
                "inputSchema": input_schema or {"type": "object", "properties": {}},
            }
        )
        return self

    def set_response(self, tool_name: str, result: Any) -> MockMCPClient:
        """Configure the response for a specific tool."""
        self._responses[tool_name] = result
        return self

    def set_default_response(self, result: Any) -> MockMCPClient:
        """Set the fallback response for unconfigured tools."""
        self._default_response = result
        return self

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth: OrchidAuthContext,
    ) -> OrchidMCPToolResult:
        self._calls.append((tool_name, arguments))
        result = self._responses.get(tool_name, self._default_response)
        if isinstance(result, OrchidMCPToolResult):
            return result
        if isinstance(result, dict):
            return OrchidMCPToolResult(content=[{"type": "text", "text": str(result)}])
        if result is None:
            return OrchidMCPToolResult(content=[])
        return OrchidMCPToolResult(content=[{"type": "text", "text": str(result)}])

    async def list_tools(self, auth: OrchidAuthContext) -> list[dict[str, Any]]:
        return list(self._tools)

    async def list_prompts(self, auth: OrchidAuthContext) -> list[dict[str, Any]]:
        return []

    async def list_resources(self, auth: OrchidAuthContext) -> list[dict[str, Any]]:
        return []

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, str],
        auth: OrchidAuthContext,
    ) -> list[dict[str, Any]]:
        return []

    async def read_resource(self, uri: str, auth: OrchidAuthContext) -> str:
        return ""

    @property
    def calls(self) -> list[tuple[str, dict[str, Any]]]:
        """History of tool calls made during the test."""
        return list(self._calls)

    def clear_calls(self) -> None:
        self._calls.clear()


class MockCacheableMCPClient(MockMCPClient, OrchidCacheableMCPClient):
    """Mock MCP client that supports proactive capability-cache warming."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cache_warmed_count = 0
        self._cache_invalidated_count = 0

    async def warm_cache(self, auth: OrchidAuthContext) -> None:
        self._cache_warmed_count += 1

    def invalidate_cache(self) -> None:
        self._cache_invalidated_count += 1

    @property
    def cache_warmed_count(self) -> int:
        return self._cache_warmed_count

    @property
    def cache_invalidated_count(self) -> int:
        return self._cache_invalidated_count


@pytest.fixture
def mock_mcp_client() -> MockMCPClient:
    """Fresh configurable MCP client."""
    return MockMCPClient()


@pytest.fixture
def mock_cacheable_mcp_client() -> MockCacheableMCPClient:
    """Fresh configurable cacheable MCP client."""
    return MockCacheableMCPClient()
