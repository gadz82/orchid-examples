"""Startup hook — register custom retrieval strategies.

Called once at Orchid bootstrap via the ``startup.hook`` YAML key.
Double-registration guard: if a strategy is already in the registry,
the registration is a no‑op (safe for hot-reload scenarios).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def bootstrap_fm_strategies(
    reader: Any,
    settings: Any,
    runtime: Any,
    agents_config: Any,
    **kwargs: Any,
) -> None:
    """Register fm-agent custom retrieval strategies and helpers.

    Called by orchids startup hook machinery.  The ``reader``,
    ``settings``, ``runtime`` and ``agents_config`` arguments are injected by the
    framework at bootstrap time; ``kwargs`` captures any future framework arguments.
    """
    from orchid_ai.guardrails.registry import GUARDRAIL_REGISTRY, register_guardrail
    from orchid_ai.rag.strategies import RETRIEVAL_REGISTRY, register_retrieval_strategy

    # Expose capture helpers via module import side-effect; the runtime bag
    # does not need mutation because agents import the module directly.
    from examples.fm_agent.hooks import capture  # noqa: F401
    from examples.fm_agent.recency_strategy import RecencyHybridRetrieval
    from examples.fm_agent.secret_guardrail import GUARDRAIL_NAME, SecretDetectionGuardrail

    if "recency_hybrid" not in RETRIEVAL_REGISTRY:
        register_retrieval_strategy("recency_hybrid", RecencyHybridRetrieval)
        logger.info("[fm-agent] Registered retrieval strategy: recency_hybrid")
    else:
        logger.info("[fm-agent] Strategy recency_hybrid already registered — no-op")

    if GUARDRAIL_NAME not in GUARDRAIL_REGISTRY:
        register_guardrail(GUARDRAIL_NAME, SecretDetectionGuardrail)
        logger.info("[fm-agent] Registered guardrail: %s", GUARDRAIL_NAME)
    else:
        logger.info("[fm-agent] Guardrail %s already registered — no-op", GUARDRAIL_NAME)

    await _diff_atlassian_allowlist(agents_config)


async def _diff_atlassian_allowlist(agents_config: Any) -> None:
    """Fail-open check that Atlassian tools are pinned in the allowlist."""
    if agents_config is None:
        logger.info("[mcp-guard] No agents_config provided; skipping allowlist diff")
        return

    from orchid_ai.core.state import OrchidAuthContext
    from orchid_ai.mcp.client import StreamableHttpMCPClient

    from examples.fm_agent.hooks.mcp_guard import enforce_atlassian_allowlist

    seen: set[str] = set()
    for agent in getattr(agents_config, "agents", {}).values():
        for server in getattr(agent, "mcp_servers", []):
            if server.name != "atlassian-rovo" or server.name in seen:
                continue
            seen.add(server.name)
            client = StreamableHttpMCPClient(
                url=server.url,
                server_type=server.type,
                transport=server.transport,
                server_name=server.name,
                auth_mode=server.auth.mode,
            )
            # Dummy auth context: the OAuth flow is not available at startup,
            # so list_tools is expected to fail; the guard is fail-open.
            auth = OrchidAuthContext(access_token="startup-dummy")
            await enforce_atlassian_allowlist(server, client, auth)

