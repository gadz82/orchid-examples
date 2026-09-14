"""Self-tests for the mock MCP client."""

from __future__ import annotations

import pytest
from examples._e2e_shared.fixtures.auth import make_auth_context
from examples._e2e_shared.fixtures.mock_mcp import MockCacheableMCPClient, MockMCPClient
from orchid_ai.core.mcp_result import OrchidMCPToolResult


@pytest.fixture
def client() -> MockMCPClient:
    return MockMCPClient()


async def test_call_tool_records_and_returns(client: MockMCPClient) -> None:
    client.add_tool("weather").set_response("weather", {"temp": 22})
    auth = make_auth_context()
    result = await client.call_tool("weather", {"city": "Rome"}, auth)
    assert isinstance(result, OrchidMCPToolResult)
    assert result.text == "{'temp': 22}"
    assert client.calls == [("weather", {"city": "Rome"})]


async def test_default_response(client: MockMCPClient) -> None:
    client.set_default_response("fallback")
    auth = make_auth_context()
    result = await client.call_tool("unknown", {}, auth)
    assert result.text == "fallback"


async def test_list_tools(client: MockMCPClient) -> None:
    client.add_tool("a").add_tool("b")
    auth = make_auth_context()
    tools = await client.list_tools(auth)
    assert [t["name"] for t in tools] == ["a", "b"]


async def test_cacheable_warm_and_invalidate() -> None:
    client = MockCacheableMCPClient()
    auth = make_auth_context()
    await client.warm_cache(auth)
    await client.warm_cache(auth)
    client.invalidate_cache()
    assert client.cache_warmed_count == 2
    assert client.cache_invalidated_count == 1
