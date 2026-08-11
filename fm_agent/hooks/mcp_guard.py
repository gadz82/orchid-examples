"""MCP allowlist guard — detect unpinned tools at connect time.

Called from the startup hook to diff the configured Atlassian tool allowlist
against the tools advertised by the server.  Fail-open: listing failures are
logged but never block bootstrap.
"""

from __future__ import annotations

import logging

from orchid_ai.config.schema_mcp import OrchidMCPServerConfig
from orchid_ai.core.mcp import OrchidMCPClient
from orchid_ai.core.state import OrchidAuthContext

logger = logging.getLogger(__name__)


async def enforce_atlassian_allowlist(
    server_config: OrchidMCPServerConfig,
    client: OrchidMCPClient,
    auth: OrchidAuthContext,
) -> list[str]:
    """Compare advertised Atlassian tools with the configured allowlist.

    Returns the list of advertised tool names that are **not** in the
    configured allowlist.  Logs a warning for each unpinned tool.
    """
    allowed_names = {t.name for t in server_config.tools}

    try:
        advertised = await client.list_tools(auth)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[mcp-guard] Could not list tools for %s; skipping allowlist diff: %s",
            server_config.name,
            exc,
        )
        return []

    advertised_names: set[str] = set()
    for tool in advertised:
        if isinstance(tool, dict):
            advertised_names.add(tool.get("name", ""))
        elif hasattr(tool, "name"):
            advertised_names.add(tool.name)

    unpinned = sorted(advertised_names - allowed_names)
    if unpinned:
        logger.warning(
            "[mcp-guard] Atlassian server advertises unpinned tools (disabled by default): %s",
            unpinned,
        )
    else:
        logger.info("[mcp-guard] All advertised Atlassian tools are allowlisted")

    return unpinned
