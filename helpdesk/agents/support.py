"""
Support Agent — agentic tool-calling loop for technical support.

Custom OrchidAgent subclass that handles technical support queries using
a multi-turn LLM loop. The agent:

1. Retrieves relevant knowledge base articles via RAG
2. Calls built-in tools (classify_ticket, search_kb, get_ticket_status)
   through the LLM's function-calling interface
3. Loops until the LLM produces a final text response
4. Returns a comprehensive support response

This demonstrates the custom agent pattern: when GenericAgent's
single-pass execution is insufficient, subclass OrchidAgent and
implement your own ``run()`` with an agentic loop.

RAG namespace: ``knowledge_base`` (tenant-aware)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage

from orchid_ai.core.agent import OrchidAgent
from orchid_ai.core.state import OrchidAgentState, OrchidAuthContext
from orchid_ai.rag.scopes import OrchidRAGScope

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8  # safety limit for the tool-calling loop

# ── Tool definitions for litellm function calling ─────────────────

_BUILTIN_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "classify_ticket",
            "description": (
                "Classify a support ticket by priority and category. "
                "Returns priority level, category, confidence score, and suggested agent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "The ticket description or problem statement to classify",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": (
                "Search the knowledge base for articles relevant to a technical issue. "
                "Returns matching articles with content and relevance scores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query describing the technical issue",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ticket_status",
            "description": (
                "Look up the current status, priority, and details of an existing support ticket."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {
                        "type": "string",
                        "description": "The ticket identifier, e.g. 'TK-1001'",
                    },
                },
                "required": ["ticket_id"],
            },
        },
    },
]


class SupportAgent(OrchidAgent):
    """
    Agentic technical support — LLM drives built-in tool calls.

    Unlike GenericAgent which executes tools in a single pass,
    SupportAgent runs a multi-turn loop where the LLM decides
    which tools to call and when to stop. This allows complex
    diagnostic workflows: classify -> search KB -> check status -> respond.
    """

    @property
    def name(self) -> str:
        return "support"

    @property
    def description(self) -> str:
        return (
            "Technical support agent. Handles troubleshooting, diagnostics, "
            "and resolution of customer issues. Can classify tickets, search "
            "the knowledge base, and check ticket status. Use for any technical "
            "support question or issue that needs investigation."
        )

    @property
    def rag_namespace(self) -> str:
        return "knowledge_base"

    # ── Main entry point ─────────────────────────────────────

    async def run(self, state: OrchidAgentState) -> OrchidAgentState:
        auth: OrchidAuthContext | None = state.get("auth_context")
        user_query = self.extract_user_query(state)

        # Check for skill instructions from the orchestrator
        skill_instructions = state.get("skill_instructions", {})
        if self.name in skill_instructions:
            instruction = skill_instructions[self.name]
            logger.info("[Support] Executing with skill instruction: %s", instruction[:100])
            user_query = f"{user_query}\n\n[Orchestrator instruction: {instruction}]"

        # Build hierarchical RAG scope
        tenant_key = auth.tenant_key if auth else "default"
        user_uuid = auth.user_id if auth else ""
        scope = OrchidRAGScope(
            tenant_id=tenant_key,
            user_id=user_uuid,
            chat_id=state.get("chat_id", ""),
            agent_id=self.name,
        )

        # 1. RAG retrieval — fetch relevant knowledge base articles
        rag_data = await self.fetch_rag_context(user_query, scope)

        # 2. Multi-turn conversation history — framework-level helper
        #    that filters supervisor-routing noise and strips agent
        #    name prefixes.  Injected between the system prompt and
        #    the current user query so follow-ups like "yes please"
        #    have the prior turns to anchor against.
        conversation_history = self.extract_conversation_history(
            state,
            max_turns=10,
            max_chars=1000,
        )

        # 3. Agentic tool-calling loop
        response_text, tool_results = await self._agentic_loop(
            user_query=user_query,
            rag_data=rag_data,
            conversation_history=conversation_history,
        )

        return {
            "messages": [AIMessage(content=f"[Support Agent]\n{response_text}")],
            "mcp_context": {"support": tool_results},
            "rag_context": {"support": rag_data},
        }

    # ── Agentic tool-calling loop ────────────────────────────

    async def _agentic_loop(
        self,
        user_query: str,
        rag_data: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Multi-turn LLM <-> tool loop.

        1. Build system prompt with RAG context
        2. Present built-in tools as litellm function definitions
        3. Loop: LLM emits tool_calls -> execute via call_builtin_tool -> feed results back
        4. Return final text response + all tool results

        ``conversation_history`` (list of ``{"role": ..., "content": ...}``
        dicts produced by ``OrchidAgent.extract_conversation_history``)
        is inserted between the system prompt and the current user
        query so multi-turn follow-ups have the prior context to
        anchor against.  Defaults to ``None`` (single-turn) so the
        callable signature remains backwards-compatible.
        """
        model = self.model_id if isinstance(self.model_id, str) else str(self.model_id)
        tool_results: dict[str, Any] = {}

        # ── Build system prompt ──────────────────────────────
        system_prompt = self._build_system_prompt(rag_data)

        # ── Conversation messages ────────────────────────────
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *(conversation_history or []),
            {"role": "user", "content": user_query},
        ]

        # ── Loop ─────────────────────────────────────────────
        # Agentic loop requires full response objects (tool_calls),
        # so we use litellm directly here — LLMProvider.complete() only returns str.
        import litellm
        from orchid_ai.llm import get_llm_kwargs

        for round_num in range(MAX_TOOL_ROUNDS):
            call_kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": 0.2,
                "tools": _BUILTIN_TOOLS_SCHEMA,
                "tool_choice": "auto",
                **get_llm_kwargs(model),
            }

            try:
                response = await litellm.acompletion(**call_kwargs)
            except Exception as exc:
                error_msg = str(exc)
                logger.error(
                    "[Support] LLM API error in round %d: %s",
                    round_num,
                    error_msg,
                    exc_info=True,
                )
                return (
                    f"I encountered an error while processing your request: {error_msg[:200]}. "
                    "Please try again later.",
                    tool_results,
                )

            choice = response.choices[0]
            assistant_msg = choice.message

            # Append assistant message to conversation history
            messages.append(assistant_msg.model_dump(exclude_none=True))

            # Check if LLM wants to call tools
            tool_calls = getattr(assistant_msg, "tool_calls", None)
            if not tool_calls:
                # No more tool calls — LLM is done
                final_text = assistant_msg.content or ""
                logger.info("[Support] LLM responded after %d tool round(s)", round_num)
                return final_text, tool_results

            # Execute each tool call via the built-in tool registry
            for tc in tool_calls:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}
                    logger.warning("[Support] Failed to parse tool arguments for '%s'", fn_name)

                logger.info(
                    "[Support] Tool call #%d -> %s | args: %s",
                    round_num + 1,
                    fn_name,
                    json.dumps(fn_args)[:200],
                )

                try:
                    result = await self.call_builtin_tool(fn_name, **fn_args)
                    result_text = json.dumps(result, indent=2, default=str)
                    logger.info(
                        "[Support] Tool call #%d <- %s | SUCCESS",
                        round_num + 1,
                        fn_name,
                    )
                except Exception as exc:
                    result_text = json.dumps({"error": str(exc)})
                    logger.error(
                        "[Support] Tool call #%d <- %s | ERROR: %s",
                        round_num + 1,
                        fn_name,
                        exc,
                        exc_info=True,
                    )

                tool_results[fn_name] = result_text

                # Feed result back to the LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })

        # Safety: max rounds exceeded
        logger.warning("[Support] Hit max tool rounds (%d)", MAX_TOOL_ROUNDS)
        return self._fallback_summary(user_query, tool_results, rag_data), tool_results

    # ── Prompt construction ──────────────────────────────────

    @staticmethod
    def _build_system_prompt(rag_data: list[dict[str, Any]]) -> str:
        """Build a system prompt enriched with RAG context."""
        parts = [
            "You are the Support Agent for the Helpdesk AI system.",
            "You handle technical support queries by investigating issues,",
            "searching the knowledge base, and providing clear resolutions.",
            "",
            "You have access to the following tools:",
            "- classify_ticket: Classify issues by priority and category",
            "- search_kb: Search the knowledge base for relevant articles",
            "- get_ticket_status: Look up existing ticket details",
            "",
            "Workflow:",
            "1. First, classify the issue to understand its priority and category",
            "2. Search the knowledge base for relevant solutions",
            "3. If a ticket ID is mentioned, look up its current status",
            "4. Synthesize all findings into a clear, actionable response",
            "",
            "Guidelines:",
            "- Always classify the issue before searching for solutions",
            "- Reference specific KB article IDs when citing solutions",
            "- If the issue is critical or cannot be resolved, recommend escalation",
            "- Be empathetic, professional, and thorough",
            "- Include step-by-step instructions when applicable",
        ]

        if rag_data:
            parts.append("\n--- Background Knowledge (RAG) ---")
            parts.append(json.dumps(rag_data, indent=2, default=str)[:3000])

        return "\n".join(parts)

    # ── Fallback summary ─────────────────────────────────────

    @staticmethod
    def _fallback_summary(
        query: str,
        tool_results: dict[str, Any],
        rag_data: list[dict[str, Any]],
    ) -> str:
        """Simple concatenation when the loop is exhausted without a final response."""
        parts = [f"Query: {query}", ""]
        if tool_results:
            parts.append("Investigation results:")
            for name, text in tool_results.items():
                parts.append(f"  {name}: {str(text)[:500]}")
        if rag_data:
            parts.append(f"\nKnowledge base context: {len(rag_data)} article(s) retrieved")
        parts.append(
            "\nNote: I was unable to complete the full analysis. "
            "Please consider escalating this issue for human review."
        )
        return "\n".join(parts)
