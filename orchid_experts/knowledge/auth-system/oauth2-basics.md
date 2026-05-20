<!-- Source: derived from orchid-website/src/content/concepts/oauth.mdx and codebase analysis -->

# OAuth 2.0 Basics

Orchid uses OAuth 2.0 for MCP server authentication and the MCP gateway. The framework follows the **MCP 2025-03-26 authorization spec** for server-to-server OAuth flows.

## Key Concepts

### Authorization Code Grant (PKCE)

The flow used for user-facing authorization:

1. Client redirects user to authorization endpoint.
2. User authenticates and grants consent.
3. Authorization code is returned to client.
4. Client exchanges code for access + refresh tokens (with PKCE code_verifier).

### Client Credentials Grant

Used for service-to-service authentication (no user involvement):

1. Client sends client_id + client_secret to token endpoint.
2. Receives access token.

### Dynamic Client Registration (DCR)

RFC 7591 — Clients register dynamically with the authorization server, avoiding manual client_id/client_secret provisioning:

1. Client sends registration request to the authorization server's `registration_endpoint`.
2. Server returns `client_id` and `client_secret`.
3. Client uses these for subsequent OAuth flows.

## OAuth in Orchid

### MCP Server OAuth

When an MCP server has `auth.mode: oauth`:

```yaml
mcp_servers:
  - name: external-crm
    url: ${CRM_MCP_URL}
    auth:
      mode: oauth
```

The framework handles the full OAuth flow automatically:

1. **Discovery (RFC 9728)** — On first 401, reads `WWW-Authenticate` header for `resource_metadata`.
2. **Metadata (RFC 8414)** — Fetches authorization server metadata.
3. **Registration (RFC 7591)** — Dynamically registers a client.
4. **Token Exchange** — Performs authorization code grant with PKCE.
5. **Token Management** — Stores tokens in `OrchidMCPTokenStore`, auto-refreshes.

### MCP Gateway OAuth

The MCP gateway (`orchid-mcp`) acts as an OAuth authorization server (AS role), enabling:

1. Dynamic client registration for MCP hosts.
2. Authorization code flow for user-facing MCP hosts.
3. Token proxy for NextAuth v5 frontend.

## Token Stores

| Store | Purpose |
|-------|---------|
| `OrchidMCPTokenStore` | Per-user outbound OAuth tokens for MCP servers. |
| `OrchidMCPClientRegistrationStore` | Per-server DCR credentials + endpoints (RFC 7591). |
| `OrchidMCPGatewayTokenStore` | Inbound issued access + refresh tokens. |
| `OrchidMCPGatewayClientStore` | Inbound DCR client registrations. |
| `OrchidMCPGatewayAuthCodeStore` | Inbound in-flight authorization codes. |

## auth-info Endpoint

The `/auth-info` endpoint exposes non-secret OAuth discovery information:

```json
{
  "authorization_endpoint": "https://auth.example.com/authorize",
  "token_endpoint": "https://auth.example.com/token",
  "registration_endpoint": "https://auth.example.com/register",
  "scopes_supported": ["read", "write"]
}
```

This is served by `OrchidAuthConfigProvider`, a pure config-resolution ABC (no network calls).

## Refresh Token Flow

When an access token expires:

1. The framework detects a 401 response or token expiry.
2. Uses the refresh token to obtain a new access token from the token endpoint.
3. Updates the token store with the new tokens.

Default `refresh_token` on `OrchidAuthExchangeClient` raises `NotImplementedError` — exchange-only consumers don't break. The `/auth-info` flag `refresh_via_api` checks the method override identity.
