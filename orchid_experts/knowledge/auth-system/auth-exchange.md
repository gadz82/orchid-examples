<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, and codebase analysis -->

# Auth Exchange

The auth exchange system handles authorization code exchange and token refresh on behalf of downstream clients. It is implemented through the `OrchidAuthExchangeClient` ABC and the `/auth/exchange-code` endpoint.

## OrchidAuthExchangeClient ABC

**File:** `orchid_ai/core/auth_config.py`

```python
class OrchidAuthExchangeClient(ABC):
    async def exchange_code(self, code: str, code_verifier: str, 
                            redirect_uri: str) -> OAuthToken: ...
    async def refresh_token(self, refresh_token: str) -> OAuthToken: ...
```

### exchange_code()

Performs the authorization code grant:

1. Receives authorization code from the client (after user authorization).
2. Exchanges the code for access + refresh tokens at the upstream token endpoint.
3. Uses PKCE `code_verifier` to prevent code interception.
4. Returns `OAuthToken` with access_token, refresh_token, expires_at.

### refresh_token()

Refreshes an expired access token:

1. Receives the refresh token.
2. Calls the upstream token endpoint with `grant_type=refresh_token`.
3. Returns new `OAuthToken`.

Default implementation raises `NotImplementedError` — exchange-only consumers don't break.

## /auth/exchange-code Endpoint

```
POST /auth/exchange-code
Content-Type: application/json

{
  "code": "authorization-code-from-upstream",
  "code_verifier": "pkce-code-verifier",
  "redirect_uri": "http://localhost:3000/callback"
}
```

Returns:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "rt_...",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

### Use Cases

- **MCP Gateway OAuth** — When an MCP host completes authorization, the gateway exchanges the code via this endpoint.
- **Next.js Frontend** — When a user authenticates via NextAuth, the frontend exchanges the code via this endpoint.
- **CLI OAuth** — When the CLI completes the browser-based OAuth flow, it exchanges the code via this endpoint.

## Token Refresh via API

The `/auth-info` endpoint advertises whether the API supports token refresh:

```json
{
  "refresh_via_api": true
}
```

When `true`, clients can refresh tokens via:

```
POST /auth/token
Content-Type: application/json

{
  "grant_type": "refresh_token",
  "refresh_token": "rt_..."
}
```

The flag is determined by checking if `OrchidAuthExchangeClient.refresh_token` is overridden (not the default `NotImplementedError`).

## Upstream Token Storage

After exchange, the upstream token pair is stored for downstream use:

```python
@dataclass
class OrchidMCPGatewayToken:
    id: str
    access_token: str
    refresh_token: str
    idp_access_token: str   # Upstream access token
    idp_refresh_token: str  # Upstream refresh token
    idp_expires_at: datetime
```

The `idp_*` fields preserve the upstream token pair so the refresh path can swap them when the downstream token expires.

## Security Considerations

- **PKCE is required** — The `code_verifier` must be validated against the `code_challenge` used in the authorization request.
- **Redirect URI validation** — The `redirect_uri` must match the one used in the authorization request.
- **Client authentication** — The API authenticates the client making the exchange request (via bearer token).
- **Token storage** — Upstream tokens are stored in the token store, not returned directly to downstream clients that shouldn't have them.
- **Scope limiting** — The API may limit which scopes are allowed for downstream clients.
