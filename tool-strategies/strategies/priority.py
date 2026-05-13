"""
Custom tool-call strategy: ``priority``.

Behaves like ``sequential`` but **short-circuits at the first
non-empty result** — useful when several tools answer the same
question and the integrator wants to fall back from a fast cache to
slower authoritative sources.

Demonstrates the integrator extension contract:

  1. Subclass :class:`OrchidToolCallStrategy`.
  2. Implement ``async execute(...)`` matching the ABC signature.
  3. Register the class via :func:`register_strategy` from a
     startup hook so the registry is populated before any agent
     invokes the strategy.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from orchid_ai.agents.strategies import OrchidToolCallStrategy

logger = logging.getLogger(__name__)


class PriorityStrategy(OrchidToolCallStrategy):
    """Call tools in declared order; stop at the first non-empty result.

    "Non-empty" is defined as: the tool's textual response, after
    stripping whitespace, is not empty AND is not the literal string
    ``"null"`` / ``"[]"`` / ``"{}"``.  Everything else (HTTP errors,
    transport failures) is treated as empty so the chain falls
    through to the next tool.
    """

    _EMPTY_SENTINELS = {"", "null", "[]", "{}"}

    async def execute(
        self,
        client,
        tools,
        query,
        auth,
        *,
        agent_name: str = "",
        **_kwargs: Any,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for tool in tools:
            try:
                args = {"query": query, **tool.arguments}
                result = await client.call_tool(tool.name, args, auth)
                text = (result.text or "").strip()
            except Exception as exc:
                logger.warning("[%s] priority: tool '%s' failed: %s", agent_name, tool.name, exc)
                results[f"{tool.name}_error"] = str(exc)
                continue

            results[tool.name] = text
            # Short-circuit on first non-empty payload.
            if self._has_payload(text):
                logger.info(
                    "[%s] priority: '%s' returned a non-empty payload — short-circuiting",
                    agent_name,
                    tool.name,
                )
                break

        return results

    @classmethod
    def _has_payload(cls, text: str) -> bool:
        if text in cls._EMPTY_SENTINELS:
            return False
        # Try parsing JSON to detect empty containers like ``{"items": []}``.
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError):
            return True
        if isinstance(parsed, (list, dict)) and not parsed:
            return False
        return True
