"""Integration tests for the weather example.

Tests:
  - Config loading (agents.yaml validates correctly)
  - Built-in tool execution (recommend_outfit, get_safety_tips, assess_weather_risk)
  - OutfitAdvisorAgent construction and name/description properties
  - OutfitAdvisorAgent._extract_weather_data() parses sibling results
  - OutfitAdvisorAgent.run() without weather data returns guidance message
  - Clothing recommendation logic for different temperature ranges
  - Safety risk assessment for various conditions
"""

from __future__ import annotations

from typing import Any

import pytest


# ── Config loading tests ────────────────────────────────────────

def test_config_loads_with_three_agents(weather_config):
    """agents.yaml must define exactly 3 agents."""
    assert "weather-forecast" in weather_config.agents
    assert "weather-alerts" in weather_config.agents
    assert "outfit-advisor" in weather_config.agents
    assert len(weather_config.agents) == 3


def test_supervisor_chat_summarization_enabled(weather_config):
    """Verify sliding-window summarization is configured."""
    assert weather_config.supervisor.history_summary_enabled is True
    assert weather_config.supervisor.history_summary_recent_turns > 0


def test_weather_forecast_has_remote_mcp(weather_config):
    """weather-forecast must have a remote MCP server configured."""
    agent = weather_config.agents["weather-forecast"]
    assert len(agent.mcp_servers) >= 1
    mcp = agent.mcp_servers[0]
    assert mcp.type == "remote"
    assert "weather-mcp" in mcp.url


def test_outfit_advisor_is_custom_agent(weather_config):
    """outfit-advisor must use a custom agent class."""
    agent = weather_config.agents["outfit-advisor"]
    assert agent.class_path is not None
    assert "OutfitAdvisorAgent" in agent.class_path


def test_orchestrator_skills_defined(weather_config):
    """Cross-agent skills must be defined."""
    assert "prepare_for_day" in weather_config.skills
    assert "emergency_check" in weather_config.skills


def test_builtin_tools_declared(weather_config):
    """Three built-in tools should be declared."""
    assert "recommend_outfit" in weather_config.tools
    assert "get_safety_tips" in weather_config.tools
    assert "assess_weather_risk" in weather_config.tools


# ── Tool execution tests ────────────────────────────────────────

@pytest.fixture(autouse=True)
def _load_tools(weather_config):
    """Load tools from config before each test, clear after."""
    from orchid_ai.config.tool_registry import clear, load_tools_from_config

    clear()
    load_tools_from_config(weather_config.tools)
    yield
    clear()


async def _run_tool(tool_name: str, **kwargs):
    """Helper: invoke a tool by name and return its result."""
    from orchid_ai.config.tool_registry import get_tool
    from orchid_ai.core.tool import OrchidToolInput

    tool = get_tool(tool_name)
    assert tool is not None, f"Tool '{tool_name}' not found in registry"

    tool_input = OrchidToolInput(
        query="test query",
        parameters=kwargs,
    )
    return await tool.invoke(tool_input)


async def test_recommend_outfit_hot_weather():
    """Outfit for hot weather (30°C)."""
    result = await _run_tool("recommend_outfit", temperature=30, precip_pct=10, wind_kmh=15, uv_index=7)
    assert result.metadata.get("error") is None
    data = result.result
    assert "conditions" in data
    assert "outfit" in data
    assert "tops" in data["outfit"]
    assert "short" in str(data["outfit"]["bottoms"]).lower() or "tank" in str(data["outfit"]["tops"]).lower()
    # UV protection should be present for index 7
    assert any("sunglasses" in a.lower() or "sunscreen" in a.lower() for a in data["outfit"]["accessories"])


async def test_recommend_outfit_cold_weather():
    """Outfit for cold weather (-5°C)."""
    result = await _run_tool("recommend_outfit", temperature=-5, precip_pct=20, wind_kmh=10, uv_index=1)
    assert result.metadata.get("error") is None
    data = result.result
    # Should have warm clothing
    assert any("coat" in item.lower() or "parka" in item.lower() or "puffer" in item.lower() for item in data["outfit"]["outerwear"])
    assert any("glove" in item.lower() for item in data["outfit"]["accessories"])


async def test_recommend_outfit_with_activity():
    """Outfit should adapt to activity type."""
    result = await _run_tool("recommend_outfit", temperature=15, precip_pct=0, wind_kmh=10, uv_index=3, activity="hiking")
    assert result.metadata.get("error") is None
    data = result.result
    assert any("hiking" in item.lower() for item in data["outfit"]["footwear"])


async def test_recommend_outfit_rainy():
    """Rainy weather should include waterproof items."""
    result = await _run_tool("recommend_outfit", temperature=12, precip_pct=80, wind_kmh=20, uv_index=1)
    assert result.metadata.get("error") is None
    data = result.result
    # Should have rain gear
    has_waterproof = any("waterproof" in str(v).lower() or "rain" in str(v).lower() or "umbrella" in str(v).lower() for v in data["outfit"].values())
    assert has_waterproof


async def test_get_safety_tips_valid_hazard():
    """Safety tips for a valid hazard type."""
    for hazard in ("heatwave", "storm", "flood", "blizzard", "hurricane", "extreme_cold"):
        result = await _run_tool("get_safety_tips", hazard=hazard)
        assert result.metadata.get("error") is None
        assert "recommendations" in result.result
        assert "immediate" in result.result["recommendations"]
        assert "preparation" in result.result["recommendations"]


async def test_get_safety_tips_unknown_hazard():
    """Unknown hazard should return an error."""
    result = await _run_tool("get_safety_tips", hazard="nonexistent_hazard")
    assert result.metadata.get("error") is not None


async def test_assess_weather_risk_low():
    """Normal conditions should be low risk."""
    result = await _run_tool("assess_weather_risk", temperature=20, wind_speed_kmh=10, precipitation_mm=0)
    assert result.metadata.get("error") is None
    assert result.result["overall_risk"] == "low"


async def test_assess_weather_risk_extreme_heat():
    """Extreme heat should be flagged."""
    result = await _run_tool("assess_weather_risk", temperature=42, wind_speed_kmh=10, precipitation_mm=0)
    assert result.metadata.get("error") is None
    assert result.result["overall_risk"] == "extreme"


async def test_assess_weather_risk_storm():
    """High wind + rain should be elevated risk."""
    result = await _run_tool("assess_weather_risk", temperature=18, wind_speed_kmh=85, precipitation_mm=55)
    assert result.metadata.get("error") is None
    assert result.result["overall_risk"] in ("high", "extreme")


async def test_assess_weather_risk_thunderstorm_by_code():
    """Thunderstorm weather code should be detected."""
    result = await _run_tool("assess_weather_risk", temperature=22, wind_speed_kmh=15, precipitation_mm=10, weather_code="thunderstorm")
    assert result.metadata.get("error") is None
    assert result.result["overall_risk"] in ("high", "extreme")


# ── OutfitAdvisorAgent tests ────────────────────────────────────

def test_outfit_agent_name_and_description():
    """Agent properties should match configuration."""
    from orchid_ai.rag.backends.null import NullVectorReader
    from examples.weather.agents.outfit import OutfitAdvisorAgent

    agent = OutfitAdvisorAgent(reader=NullVectorReader())
    assert agent.name == "outfit-advisor"
    assert "outfit" in agent.description.lower()
    assert agent.rag_namespace == "clothing-guides"


def test_extract_weather_data_from_forecast():
    """_extract_weather_data should parse forecast-style sibling data."""
    from examples.weather.agents.outfit import OutfitAdvisorAgent

    sibling = {
        "weather-forecast": {
            "result": {
                "temperature_c": 22,
                "precipitation_chance": 30,
                "wind_speed_kmh": 15,
                "condition": "Partly cloudy",
                "uv_index": 5,
                "humidity": 65,
                "location": "London",
            }
        }
    }

    result = OutfitAdvisorAgent._extract_weather_data(sibling)
    assert result is not None
    assert result["temperature_c"] == 22
    assert result["condition"] == "Partly cloudy"
    assert result["location"] == "London"


def test_extract_weather_data_empty():
    """Empty sibling data should return None."""
    from examples.weather.agents.outfit import OutfitAdvisorAgent

    assert OutfitAdvisorAgent._extract_weather_data({}) is None


def test_extract_weather_data_irrelevant():
    """Non-weather sibling data should return None."""
    from examples.weather.agents.outfit import OutfitAdvisorAgent

    sibling = {"some-other-agent": {"result": {"unrelated": "data"}}}
    assert OutfitAdvisorAgent._extract_weather_data(sibling) is None


async def test_outfit_agent_run_no_data(auth_context):
    """Agent without weather data should return guidance message."""
    from orchid_ai.rag.backends.null import NullVectorReader
    from examples.weather.agents.outfit import OutfitAdvisorAgent

    agent = OutfitAdvisorAgent(reader=NullVectorReader())
    state: dict[str, Any] = {
        "messages": [],
        "mcp_context": {},
    }

    # Auth is execution context — bind it on the run-context ContextVar
    # (the graph node wrapper does this in production).
    from orchid_ai.core.agent import OrchidAgentRunContext

    token = agent.set_run_context(OrchidAgentRunContext(auth=auth_context))
    try:
        result = await agent.run(state)
    finally:
        agent.reset_run_context(token)
    messages = result.get("messages", [])
    assert len(messages) > 0
    content = messages[0].content if hasattr(messages[0], "content") else str(messages[0])
    assert "forecast" in content.lower() or "weather" in content.lower() or "prepare_for_day" in content.lower()


def test_risk_order_logic():
    """Verify risk level ordering helper."""
    from examples.weather.tools.safety import _risk_summary

    low = _risk_summary("low")
    high = _risk_summary("high")
    extreme = _risk_summary("extreme")
    assert "normal" in low.lower()
    assert "dangerous" in high.lower()
    assert "life-threatening" in extreme.lower() or "seek shelter" in extreme.lower()
