"""
Startup hook for the tool-strategies example.

Registers the custom :class:`PriorityStrategy` so any agent declaring
``tool_call_strategy: priority`` on its MCP server resolves through
the registry without runtime errors.

Wire-up (orchid.yml)::

    startup:
      hook: examples.tool-strategies.hooks.startup.bootstrap_strategies
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def bootstrap_strategies(reader: Any, settings: Any, **_: Any) -> None:
    """Register the ``priority`` strategy in :data:`STRATEGY_REGISTRY`.

    Signature matches the orchid-api / orchid-cli ``STARTUP_HOOK``
    contract: ``async (reader, settings, **)``.  Neither argument is
    used here — the hook only mutates the strategy registry.
    """
    # Local imports keep startup-time cost low when this hook is
    # disabled.  The example folder is named ``tool-strategies`` (with a
    # hyphen, matching the rest of ``examples/``); Python's import
    # statement can't parse hyphenated identifiers, so we go through
    # :func:`importlib.import_module`, which accepts arbitrary dotted
    # path strings at runtime.
    import importlib

    from orchid_ai.agents.strategies import register_strategy

    priority_module = importlib.import_module(
        "examples.tool-strategies.strategies.priority",
    )
    register_strategy("priority", priority_module.PriorityStrategy)
    logger.info("[ToolStrategies] Registered custom strategy: priority")
