"""API-level e2e scenarios for the tool-strategies example.

The example is normally backed by an MCP server exposing
``cache_lookup``, ``primary_lookup``, and ``slow_lookup``.  For
offline tests we inject a mock MCP client factory that returns
predictable answers.
"""

from __future__ import annotations

from typing import Any

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.fixtures.mock_mcp import MockCacheableMCPClient
from examples._e2e_shared.fixtures.mock_vector import InMemoryVectorStore
from examples._e2e_shared.plugin import build_orchid_test_app

# ── helpers ────────────────────────────────────────────────────


def _create_chat(client) -> str:
    resp = client.post(
        "/chats",
        json={},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def _send_message(client, chat_id: str, message: str) -> dict:
    resp = client.post(
        f"/chats/{chat_id}/messages",
        data={"message": message},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert resp.status_code == 200
    return resp.json()


def _mock_mcp_factory() -> MockCacheableMCPClient:
    """Return a mock MCP client with the three knowledge-base tools."""
    client = (
        MockCacheableMCPClient(url="http://localhost/mcp")
        .add_tool("cache_lookup", "Fast cache lookup", {"type": "object", "properties": {}})
        .add_tool("primary_lookup", "Primary DB lookup", {"type": "object", "properties": {}})
        .add_tool("slow_lookup", "Slow upstream lookup", {"type": "object", "properties": {}})
        .set_response("cache_lookup", "cache hit")
        .set_response("primary_lookup", "primary result")
        .set_response("slow_lookup", "slow result")
    )
    return client


def _mcp_client_factory(server_config: Any) -> MockCacheableMCPClient:
    """Factory compatible with OrchidRuntime.get_mcp_client_factory."""
    return _mock_mcp_factory()


# ── scenarios ──────────────────────────────────────────────────


@pytest.mark.example("tool-strategies")
async def test_health(in_memory_vector_store: InMemoryVectorStore) -> None:
    """The diagnostics endpoint reports the service is healthy."""
    async with build_orchid_test_app(
        example="tool-strategies",
        vector_store=in_memory_vector_store,
        mcp_client_factory=_mcp_client_factory,
        extra_env={"KB_MCP_URL": "http://localhost/mcp"},
    ) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok"


@pytest.mark.example("tool-strategies")
async def test_priority_strategy_is_registered(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The startup hook registers the custom ``priority`` strategy."""
    from orchid_ai.agents.strategies import STRATEGY_REGISTRY

    async with build_orchid_test_app(
        example="tool-strategies",
        vector_store=in_memory_vector_store,
        mcp_client_factory=_mcp_client_factory,
        extra_env={"KB_MCP_URL": "http://localhost/mcp"},
    ):
        assert "priority" in STRATEGY_REGISTRY


@pytest.mark.example("tool-strategies")
async def test_fanout_lookup_skill_calls_mcp_tools(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """A fanout_lookup skill invocation reaches the mock MCP tools."""
    factory = FakeChatModelFactory()
    # 1. Supervisor structured routing -> fanout_lookup agent.
    factory.add_structured_response(
        reasoning="User wants a fan-out lookup",
        execution="sequential",
        agents=["fanout_lookup"],
    )
    # 2. Skill detection -> choose the lookup_everywhere skill.
    factory.add_text("lookup_everywhere")
    # 3. Final synthesis after tool calls.
    factory.add_text("Combined result: cache hit, primary result, slow result.")

    mock_client = _mock_mcp_factory()

    def _factory(cfg: Any) -> MockCacheableMCPClient:
        return mock_client

    async with build_orchid_test_app(
        example="tool-strategies",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
        mcp_client_factory=_factory,
        extra_env={"KB_MCP_URL": "http://localhost/mcp"},
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Look up everything")
        assert data["response"]
        # The exact wording depends on the fake model response above.
        assert "Combined result" in data["response"]
        # At least one MCP tool was called during skill execution.
        assert any(call[0] in {"cache_lookup", "primary_lookup", "slow_lookup"} for call in mock_client.calls)


@pytest.mark.example("tool-strategies")
async def test_parallel_searcher_agent_responds(
    in_memory_vector_store: InMemoryVectorStore,
) -> None:
    """The parallel_searcher agent boots and answers without MCP."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="User wants a metrics summary",
        execution="sequential",
        agents=["parallel_searcher"],
    )
    factory.add_text("Metrics summary: A=0.42, B=12.0, C=3.14")

    async with build_orchid_test_app(
        example="tool-strategies",
        vector_store=in_memory_vector_store,
        chat_model=factory.build(),
        mcp_client_factory=_mcp_client_factory,
        extra_env={"KB_MCP_URL": "http://localhost/mcp"},
    ) as client:
        chat_id = _create_chat(client)
        data = _send_message(client, chat_id, "Show me the metrics")
        assert data["response"]
        assert "summary" in data["response"].lower()


@pytest.mark.example("tool-strategies")
async def test_priority_strategy_short_circuits() -> None:
    """The custom priority strategy stops at the first non-empty result."""
    import importlib

    from orchid_ai.core.state import OrchidAuthContext

    priority_module = importlib.import_module(
        "examples.tool-strategies.strategies.priority"
    )
    PriorityStrategy = priority_module.PriorityStrategy

    calls: list[str] = []

    class _FakeClient:
        async def call_tool(self, name: str, arguments: dict[str, Any], auth: OrchidAuthContext):
            calls.append(name)
            if name == "primary_lookup":
                return type("R", (), {"text": "primary result"})()
            return type("R", (), {"text": ""})()

    strategy = PriorityStrategy()
    from orchid_ai.config.schema import OrchidToolConfig

    tools = [
        OrchidToolConfig(name="cache_lookup"),
        OrchidToolConfig(name="primary_lookup"),
        OrchidToolConfig(name="slow_lookup"),
    ]
    auth = OrchidAuthContext(access_token="x", tenant_key="default", user_id="u")
    result = await strategy.execute(_FakeClient(), tools, "q", auth)

    assert result.get("cache_lookup") == ""
    assert result.get("primary_lookup") == "primary result"
    assert "slow_lookup" not in result
    assert calls == ["cache_lookup", "primary_lookup"]
