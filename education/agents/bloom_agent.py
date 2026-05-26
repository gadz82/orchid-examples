"""
EducationAgent — offloads long content generation to Bloom background execution.

First call: checks if source content exceeds ``_CONTENT_THRESHOLD_CHARS``.
If long, emits ``education.content_request`` signal and returns background
message.  If short, runs inline via ``GenericAgent.run()``.

Bloom re-invokes this agent with a ``[bloom]`` marker; the agent strips
the marker, applies the ``chat_id`` override for RAG scoping, and delegates
to ``GenericAgent.run()``.
"""

from __future__ import annotations

import logging


from langchain_core.messages import AIMessage

from orchid_ai.agents.generic_agent import GenericAgent
from orchid_ai.core.state import OrchidAgentState, OrchidAuthContext
from orchid_ai.rag.scopes import OrchidRAGScope

logger = logging.getLogger(__name__)

_BLOOM_MARKER = "[bloom]"
_CONTENT_THRESHOLD_CHARS = 200000  # only offload when source content exceeds this


class EducationAgent(GenericAgent):
    """GenericAgent subclass that offloads content generation to Bloom."""

    async def run(self, state: OrchidAgentState) -> OrchidAgentState:
        query = self.extract_user_query(state)
        if not query:
            logger.info("[%s] No query — delegating to GenericAgent", self.name)
            return await super().run(state)

        # Bloom re-invocation — strip marker, apply chat_id, run normally
        if query.startswith(_BLOOM_MARKER):
            logger.info("[%s] Detected [bloom] marker — running Bloom re-invocation", self.name)
            return await self._run_bloom(state, query)

        # Check if source content is long enough to warrant background execution
        if await self._is_content_long(state):
            logger.info("[%s] Content exceeds threshold — offloading to Bloom", self.name)
            return await self._emit_and_return_background(state, query)

        logger.info("[%s] Content below threshold — running inline", self.name)
        return await super().run(state)

    async def _is_content_long(self, state: OrchidAgentState) -> bool:
        auth: OrchidAuthContext | None = state.get("auth_context")
        if not auth:
            return False
        query = self.extract_user_query(state)
        if not query:
            return False

        scope = OrchidRAGScope(
            tenant_id=auth.tenant_key,
            user_id=auth.user_id,
            chat_id=state.get("chat_id", ""),
            agent_id=self.name,
        )
        rag_data = await self.fetch_all_rag_context(query, scope, k=20)
        total_chars = sum(len(d.get("content", "")) for d in rag_data)
        return total_chars > _CONTENT_THRESHOLD_CHARS

    async def _run_bloom(
        self,
        state: OrchidAgentState,
        query: str,
    ) -> OrchidAgentState:
        """Strip [bloom] header, apply chat_id, delegate to GenericAgent.run()."""
        lines = query.split("\n")
        kept: list[str] = []

        for line in lines:
            if line.startswith(_BLOOM_MARKER):
                continue
            if line.startswith("chat_id:"):
                chat_id = line.split(":", 1)[1].strip()
                if chat_id:
                    state["chat_id"] = chat_id
                continue
            kept.append(line)

        clean_query = "\n".join(kept).strip()

        # Replace last HumanMessage content with the cleaned query
        messages = list(state.get("messages") or [])
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if getattr(msg, "type", None) == "human":
                msg.content = clean_query
                break

        return await super().run(state)

    async def _emit_and_return_background(
        self,
        state: OrchidAgentState,
        query: str,
    ) -> OrchidAgentState:
        """Emit Bloom signal and return a placeholder — Bloom produces the real content."""
        try:
            await self.emit_signal(
                "education.content_request",
                {"query": query},
                chat_id="self",
            )
            logger.info(
                "[%s] Emitted education.content_request — Bloom will process",
                self.name,
            )
        except Exception:
            logger.info(
                "[%s] emit_signal unavailable — running inline instead",
                self.name,
            )
            return await super().run(state)

        response_text = (
            f"[{self.name.title()} Agent]\n"
            "I've started generating your educational content "
            "in the background. It will appear here shortly!"
        )
        return {
            "messages": [AIMessage(content=response_text)],
            "final_response": response_text,
            "pending_agents": [],
        }
