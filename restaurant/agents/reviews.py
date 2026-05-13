"""
Custom ReviewsAgent — analyzes customer reviews using RAG context + LLM.

Demonstrates:
- Custom OrchidAgent subclass (when YAML-only GenericAgent isn't enough)
- RAG retrieval for historical review context
- Built-in tool invocation (analyze_sentiment)
- Combining RAG context with live tool results in LLM summarisation

Referenced in agents.yaml as:
    class: examples.restaurant.agents.reviews.ReviewsAgent
"""

from __future__ import annotations

import json
import logging
from typing import Any

from orchid_ai.core.agent import OrchidAgent
from orchid_ai.core.state import OrchidAgentState
from orchid_ai.rag.scopes import OrchidRAGScope

logger = logging.getLogger(__name__)


class ReviewsAgent(OrchidAgent):
    """
    Analyzes customer reviews by combining:
    1. Sentiment analysis via the ``analyze_sentiment`` built-in tool
    2. Historical review context from RAG (namespace: "reviews")
    3. LLM summarisation to produce actionable insights

    This agent showcases the custom-class pattern: override ``run()``
    with domain-specific orchestration logic that goes beyond what
    GenericAgent's YAML-driven pipeline can express.
    """

    @property
    def name(self) -> str:
        return "reviews"

    @property
    def description(self) -> str:
        return (
            "Analyzes customer reviews and feedback. Performs sentiment analysis, "
            "identifies trends, and provides actionable insights for restaurant improvement. "
            "Use for review analysis, feedback summaries, and satisfaction metrics."
        )

    @property
    def rag_namespace(self) -> str:
        return "reviews"

    async def run(self, state: OrchidAgentState) -> OrchidAgentState:
        """
        1. Extract user query
        2. Retrieve historical reviews from RAG for context
        3. Run sentiment analysis on the provided review text
        4. Summarise findings with LLM
        """
        query = self.extract_user_query(state)
        if not query:
            state["final_response"] = "I need a review or question about reviews to analyze."
            return state

        auth = state.get("auth_context")

        # -- Step 1: Retrieve historical review context from RAG --------
        rag_docs: list[dict[str, Any]] = []
        if auth:
            scope = OrchidRAGScope(
                tenant_id=auth.tenant_key,
                user_id=auth.user_id,
                chat_id=state.get("chat_id", ""),
                agent_id=self.name,
            )
            rag_docs = await self.fetch_rag_context(query, scope, k=5)
            logger.info("[reviews] Retrieved %d historical review docs from RAG", len(rag_docs))

        # -- Step 2: Run sentiment analysis on the query text -----------
        sentiment_result: dict[str, Any] = {}
        try:
            sentiment_result = await self.call_builtin_tool("analyze_sentiment", text=query)
            logger.info("[reviews] Sentiment analysis: %s", sentiment_result.get("sentiment", "unknown"))
        except Exception as exc:
            logger.warning("[reviews] Sentiment tool failed: %s", exc)
            sentiment_result = {"error": str(exc)}

        # -- Step 3: Merge into mcp_context for downstream use ----------
        mcp_data = dict(state.get("mcp_context") or {})
        mcp_data["reviews"] = {
            "sentiment_analysis": sentiment_result,
            "rag_context_count": len(rag_docs),
        }
        state["mcp_context"] = mcp_data

        rag_context = dict(state.get("rag_context") or {})
        rag_context["reviews"] = rag_docs
        state["rag_context"] = rag_context

        # -- Step 4: LLM summarisation ----------------------------------
        system_prompt = (
            "You are a Restaurant Review Analyst. Analyze customer feedback and provide "
            "actionable insights. Consider sentiment scores, recurring themes, and specific "
            "praise or complaints. When historical review data is available, identify trends "
            "and compare the current review against past patterns.\n\n"
            "Structure your response with:\n"
            "- Sentiment summary (positive/negative/mixed)\n"
            "- Key themes identified\n"
            "- Specific feedback highlights\n"
            "- Actionable recommendations for the restaurant"
        )

        try:
            summary = await self.summarise(
                query=query,
                mcp_data={"sentiment": sentiment_result},
                rag_data=rag_docs,
                system_prompt=system_prompt,
            )
            state["final_response"] = summary
        except Exception as exc:
            logger.error("[reviews] LLM summarisation failed: %s", exc)
            # Fallback: return raw analysis
            state["final_response"] = (
                f"**Sentiment Analysis Result:**\n"
                f"```json\n{json.dumps(sentiment_result, indent=2)}\n```\n\n"
                f"Historical context: {len(rag_docs)} related reviews found."
            )

        return state
