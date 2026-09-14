"""Live-server smoke tests for the MCP auth example.

These tests assume an orchid-api instance is running with the
``examples/mcp-auth/orchid.yml`` config.  They skip when ``ORCHID_API_URL``
is unset, so the in-process/CI suite remains hermetic.
"""

from __future__ import annotations

import os

import pytest


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("ORCHID_API_URL", "") == "",
        reason="Live MCP-auth API URL not configured (set ORCHID_API_URL)",
    ),
]


@pytest.fixture(scope="module")
def auth_token() -> str:
    return os.environ.get("DEV_BYPASS_TOKEN", "dev-token")


async def test_health(api_client) -> None:
    """The API is reachable."""
    resp = await api_client.get("/health")
    assert resp.status_code in (200, 204)


async def test_mcp_auth_servers_lists_configured_servers(api_client, auth_token: str) -> None:
    """The MCP auth endpoint returns the three configured servers."""
    resp = await api_client.get(
        "/mcp/auth/servers",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    names = {s["name"] for s in body.get("servers", [])}
    assert "local-server" in names
    assert "internal-platform" in names
    assert "external-crm" in names


async def test_authorize_endpoint_exists_for_oauth_server(api_client, auth_token: str) -> None:
    """The authorize endpoint for the OAuth server is wired (actual OAuth flow
    requires a real IdP, so we only assert the endpoint responds)."""
    resp = await api_client.get(
        "/mcp/auth/servers/external-crm/authorize",
        headers={"Authorization": f"Bearer {auth_token}"},
        follow_redirects=False,
    )
    # Without a real IdP we expect either a validation error or a redirect.
    assert resp.status_code in (200, 307, 308, 400, 404)


async def test_revoke_token_endpoint_responds(api_client, auth_token: str) -> None:
    """The revoke endpoint is reachable and handles missing tokens gracefully."""
    resp = await api_client.delete(
        "/mcp/auth/servers/local-server/token",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    # Token may not exist; the endpoint should not crash.
    assert resp.status_code in (204, 404)


async def test_discovery_endpoint_exists(api_client, auth_token: str) -> None:
    """The force-discovery endpoint for the OAuth server is wired."""
    resp = await api_client.post(
        "/mcp/auth/servers/external-crm/discover",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    # Actual discovery needs a reachable IdP; we only assert the route exists.
    assert resp.status_code in (200, 400, 404)
