"""
ItineraryAgent — custom OrchidAgent subclass demonstrating:
  - Subclassing OrchidAgent (not GenericAgent)
  - Custom ``run()`` logic that inspects state
  - Reusing inherited helpers (``extract_user_query``, ``fetch_rag_context``,
    ``extract_conversation_history``, ``summarise``)
  - Accessing ``mcp_context`` (results from sibling agents) in ``state``

This agent does NOT call tools directly.  Instead, it reads results already
gathered by the ``flights`` and ``hotels`` agents (via ``state["mcp_context"]``)
and synthesises a day-by-day itinerary grounded in those results.

Per-agent rule: NEVER invent flight numbers, hotel IDs, prices, or dates
that aren't in the available tool results.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage

from orchid_ai.core.agent import OrchidAgent
from orchid_ai.core.state import OrchidAgentState, OrchidAuthContext
from orchid_ai.rag.scopes import OrchidRAGScope

logger = logging.getLogger(__name__)


_ITINERARY_PROMPT = (
    "You are an expert travel itinerary planner.\n\n"
    "CRITICAL GROUNDING RULES:\n"
    "- ONLY reference flights, hotels, prices, and dates that appear in "
    "the 'Sibling agent data' section below.\n"
    "- NEVER invent flight numbers, hotel names, IDs, or prices.\n"
    "- If information is missing, say so explicitly and suggest what to "
    "ask the user next.\n\n"
    "Produce a concise, day-by-day plan that:\n"
    "- Opens with a one-line summary (destination + dates + budget estimate)\n"
    "- Lists each day with activities matching the traveller's interests\n"
    "- Cites flight numbers and hotel IDs verbatim from the source data\n"
    "- Ends with a booking checklist (flights, hotels, activities)\n"
)


class ItineraryAgent(OrchidAgent):
    """Synthesises a multi-day travel plan from sibling agent results.

    Uses ``state["mcp_context"]`` to read flight/hotel search results
    gathered by the other agents, plus optional RAG context for
    destination guides.
    """

    def __init__(self, *, config: Any = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._config = config

    @property
    def name(self) -> str:
        return "itinerary"

    @property
    def description(self) -> str:
        return (
            "Itinerary planner.  Synthesises a day-by-day travel plan grounded "
            "in flight and hotel search results from sibling agents, plus "
            "destination RAG context.  Use after flight/hotel search is complete."
        )

    @property
    def rag_namespace(self) -> str:
        return "destinations"

    async def run(self, state: OrchidAgentState) -> OrchidAgentState:
        auth: OrchidAuthContext | None = state.get("auth_context")
        if auth is None:
            return {"messages": [AIMessage(content="[Itinerary] Missing auth_context.")]}

        # ── Inherited helper: extract the user's latest query ──
        query = self.extract_user_query(state)

        # ── Read sibling agent results (flights + hotels) from state ──
        mcp_context = state.get("mcp_context", {}) or {}
        sibling_data = {
            agent: data for agent, data in mcp_context.items() if agent != self.name
        }

        if not sibling_data:
            msg = (
                "[Itinerary] I can build you a plan once we have flight and "
                "hotel options. Please search those first."
            )
            return {"messages": [AIMessage(content=msg)]}

        # ── Fetch destination RAG context (uses multi-query via parent class) ──
        scope = OrchidRAGScope(
            tenant_id=auth.tenant_key,
            user_id=auth.user_id,
            chat_id=state.get("chat_id", ""),
            agent_id=self.name,
        )
        rag_data = await self.fetch_rag_context(query, scope, k=5)

        # ── Inherited helper: clean multi-turn history ──
        history = self.extract_conversation_history(state, max_turns=5, max_chars=800)

        # ── Inherited helper: LLM summarisation ──
        summary = await self.summarise(
            query=query,
            mcp_data=sibling_data,
            rag_data=rag_data,
            system_prompt=_ITINERARY_PROMPT,
            conversation_history=history or None,
        )

        return {
            "messages": [AIMessage(content=summary, name=self.name)],
            "mcp_context": {self.name: {"itinerary": summary}},
            "rag_context": {self.name: rag_data},
        }
