"""OutfitAdvisorAgent — custom OrchidAgent subclass demonstrating:

  - Subclassing OrchidAgent (not GenericAgent)
  - Custom ``run()`` logic that reads weather data from sibling agents
  - Reusing inherited helpers (``extract_user_query``, ``fetch_rag_context``,
    ``extract_conversation_history``, ``summarise``)
  - Accessing ``mcp_context`` (results from sibling agents) in ``state``
  - RAG-augmented clothing recommendations

This agent does NOT call MCP tools directly. Instead, it reads weather results
already gathered by the ``weather-forecast`` agent (via ``state["mcp_context"]``)
and synthesises outfit recommendations grounded in weather data + RAG knowledge.

Per-agent rule: ONLY reference clothing items that match the actual weather
conditions from sibling agent results. NEVER suggest outfits without weather data.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage

from orchid_ai.core.agent import OrchidAgent
from orchid_ai.core.state import OrchidAgentState, OrchidAuthContext
from orchid_ai.rag.scopes import OrchidRAGScope

logger = logging.getLogger(__name__)

_OUTFIT_PROMPT = (
    "You are an expert outfit advisor AI assistant.\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "- ONLY recommend clothing that matches the weather data provided below.\n"
    "- NEVER suggest outfits without temperature, precipitation, and wind data.\n"
    "- Consider the full day: morning, midday, and evening conditions.\n"
    "- Mention layering options for temperature swings.\n"
    "- If the user has a specific activity, adapt the outfit accordingly.\n\n"
    "Produce a concise outfit recommendation that:\n"
    "- Opens with a one-line weather summary (temp, conditions, wind)\n"
    "- Lists each clothing category with specific items and reasoning\n"
    "- Includes essential accessories (umbrella, sunscreen, etc.)\n"
    "- Notes any weather-related cautions (e.g. 'dress in layers for the 10°C drop at night')\n"
    "- Ends with a quick-check list for the user\n"
)

_NO_DATA_MSG = (
    "[Outfit Advisor] I can recommend an outfit once I know the weather conditions. "
    "Please ask the weather-forecast agent to get the forecast first, or use the "
    "'prepare_for_day' skill for a complete morning briefing."
)


class OutfitAdvisorAgent(OrchidAgent):
    """Synthesises outfit recommendations from weather data and RAG clothing guides.

    Uses ``state["mcp_context"]`` to read weather forecast results gathered by
    the weather-forecast agent, plus RAG context for clothing guidelines.
    """

    def __init__(self, *, config: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = config

    @property
    def name(self) -> str:
        return "outfit-advisor"

    @property
    def description(self) -> str:
        return (
            "Outfit advisor. Recommends clothing, footwear, and accessories based on "
            "weather conditions (temperature, precipitation, wind, UV). Uses weather "
            "data from sibling agents and RAG clothing guides. Use after getting the "
            "weather forecast."
        )

    @property
    def rag_namespace(self) -> str:
        return "clothing-guides"

    async def run(self, state: OrchidAgentState) -> OrchidAgentState:
        auth: OrchidAuthContext | None = state.get("auth_context")
        if auth is None:
            return {"messages": [AIMessage(content="[Outfit Advisor] Missing auth_context.")]}

        # ── Inherited helper: extract the user's latest query ──
        query = self.extract_user_query(state)

        # ── Read sibling agent results (weather-forecast) from state ──
        mcp_context = state.get("mcp_context", {}) or {}
        sibling_data = {
            agent: data for agent, data in mcp_context.items() if agent != self.name
        }

        # ── Try to extract weather data from sibling results ──
        weather_data = self._extract_weather_data(sibling_data)

        if not weather_data:
            # Check if the built-in recommend_outfit tool was used directly
            if state.get("messages"):
                result = {}
                result["messages"] = [AIMessage(content=_NO_DATA_MSG, name=self.name)]
                return result
            result2: OrchidAgentState = {"messages": [AIMessage(content=_NO_DATA_MSG, name=self.name)]}
            return result2

        # ── Fetch RAG clothing guides ──
        scope = OrchidRAGScope(
            tenant_id=auth.tenant_key,
            user_id=auth.user_id,
            chat_id=state.get("chat_id", ""),
            agent_id=self.name,
        )
        rag_data = await self.fetch_rag_context(query, scope, k=3)

        # ── Inherited helper: clean multi-turn history ──
        history = self.extract_conversation_history(state, max_turns=10, max_chars=1000)

        # ── Inherited helper: LLM summarisation ──
        summary = await self.summarise(
            query=query,
            mcp_data=weather_data,
            rag_data=rag_data,
            system_prompt=_OUTFIT_PROMPT,
            conversation_history=history or None,
        )

        return {
            "messages": [AIMessage(content=summary, name=self.name)],
            "mcp_context": {self.name: {"outfit_recommendation": summary}},
            "rag_context": {self.name: rag_data},
        }

    @staticmethod
    def _extract_weather_data(sibling_data: dict[str, Any]) -> dict[str, Any] | None:
        """Pull weather conditions from sibling agent tool results.

        Reads through mcp_context entries from weather-forecast and weather-alerts
        to find temperature, precipitation, wind, and condition data.
        """
        if not sibling_data:
            return None

        weather_info: dict[str, Any] = {}

        for _agent, data in sibling_data.items():
            if not isinstance(data, (dict, list)):
                continue

            # Data could be a dict of tool results or a list
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue

                # Look for forecast data in the nested results
                result = item.get("result", item)
                if not isinstance(result, dict):
                    continue

                # Extract weather parameters
                for key in ("temperature_c", "temperature", "temp_c", "current_temp"):
                    if key in result:
                        weather_info["temperature_c"] = result[key]
                        break

                for key in ("precipitation_chance", "precip_pct", "rain_chance", "precipitation_probability"):
                    if key in result:
                        weather_info["precipitation_chance"] = result[key]
                        break

                for key in ("wind_speed_kmh", "wind_speed", "wind_kmh"):
                    if key in result:
                        weather_info["wind_speed_kmh"] = result[key]
                        break

                for key in ("weather_condition", "condition", "weather_code", "summary"):
                    if key in result:
                        weather_info["condition"] = result[key]
                        break

                for key in ("uv_index", "uv"):
                    if key in result:
                        weather_info["uv_index"] = result[key]
                        break

                for key in ("humidity", "relative_humidity"):
                    if key in result:
                        weather_info["humidity"] = result[key]
                        break

                for key in ("forecast", "daily", "daily_forecast"):
                    if key in result:
                        weather_info["forecast"] = result[key]
                        break

                for key in ("city", "location", "location_name"):
                    if key in result:
                        weather_info["location"] = result[key]
                        break

        # Only consider valid if we have at least temperature
        if "temperature_c" not in weather_info and "forecast" not in weather_info:
            return None

        return weather_info
