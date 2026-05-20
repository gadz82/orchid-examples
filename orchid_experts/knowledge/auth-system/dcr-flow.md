<!-- Source: derived from orchid-website/src/content/concepts/oauth.mdx, orchid/AGENTS.md, and codebase analysis -->

# DCR Flow

Dynamic Client Registration (DCR) is defined by RFC 7591 and allows OAuth clients to register dynamically with an authorization server, avoiding manual `client_id` and `client_secret` provisioning.

## DCR in Orchid

When an MCP server has `auth.mode: oauth`, the framework automatically performs DCR as part of the OAuth flow.

### Flow

1. **401 Response** — The MCP server returns 401 with `WWW-Authenticate: Bearer resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"`.
2. **Resource Metadata (RFC 9728)** — The framework fetches the resource metadata to discover the authorization server.
3. **Authorization Server Metadata (RFC 8414)** — The framework fetches `/.well-known/oauth-authorization-server` to get endpoints.
4. **Dynamic Client Registration (RFC 7591)** — The framework calls the `registration_endpoint` with a registration request.
5. **Store Credentials** — The returned `client_id`, `client_secret`, and endpoints are persisted to `OrchidMCPClientRegistrationStore`.

### Registration Request

```json
{
  "client_name": "Orchid MCP Client",
  "redirect_uris": ["http://localhost:0/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "token_endpoint_auth_method": "client_secret_basic",
  "scope": "read write"
}
```

### Registration Response

```json
{
  "client_id": "s6BhdRkqt3",
  "client_secret": "CFJgd8hG...",
  "client_id_issued_at": 1680000000,
  "registration_client_uri": "https://auth.example.com/register/s6BhdRkqt3"
}
```

## PKCE (Proof Key for Code Exchange)

After DCR, the authorization code flow uses PKCE for security:

1. Generate `code_verifier` (random string, 43-128 chars).
2. Derive `code_challenge` = `SHA256(code_verifier)`, base64url-encoded.
3. Include `code_challenge` in the authorization request.
4. Include `code_verifier` in the token exchange request.

PKCE prevents authorization code interception attacks.

## Token Lifecycle

After the authorization code exchange:

1. **Access Token** — Short-lived (typically 1 hour), used for API calls.
2. **Refresh Token** — Long-lived (hours to days), used to obtain new access tokens.
3. **Auto-Refresh** — The framework detects 401s and automatically refreshes expired tokens.

Tokens are stored in `OrchidMCPTokenStore`.

## Prerequisites for DCR

The authorization server MUST advertise `registration_endpoint` in its RFC 8414 metadata:

```json
{
  "registration_endpoint": "https://auth.example.com/register"
}
```

If the endpoint is missing, discovery fails with a clear error.

### Manual Registration (No DCR)

For IdPs without DCR support:

1. Manually register a client with the IdP (get `client_id` and `client_secret`).
2. Seed `OrchidMCPClientRegistrationStore` with the credentials + endpoints before first use:

```python
await registration_store.store(
    server_name="external-crm",
    client_id="manual-client",
    client_secret="manual-secret",
    token_endpoint="https://auth.example.com/token",
    authorization_endpoint="https://auth.example.com/authorize",
)
```

Then configure the server with `auth.mode: oauth` as usual.

## DCR in the MCP Gateway

The MCP gateway (`orchid-mcp`) also supports DCR in the AS (Authorization Server) role:

- MCP hosts register dynamically with the gateway.
- The gateway stores DCR client registrations in `OrchidMCPGatewayClientStore`.
- Registered clients can then perform OAuth flows with the gateway.

This enables the full MCP authorization spec: any MCP host can discover and register with Orchid without pre-shared credentials.
