<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# OAuth CLI

The CLI supports OAuth token management for authenticating with Orchid deployments that require real authentication. Tokens are stored securely on disk with restricted file permissions.

## Login Flow

```bash
orchid auth login --config orchid.yml
```

The flow:
1. CLI reads OIDC configuration from `orchid.yml` (issuer, client_id).
2. Generates a PKCE `code_verifier` and `code_challenge` (S256).
3. Starts a local HTTP server on a random port for the callback.
4. Opens the browser to the authorization URL with scope, redirect_uri, and code_challenge.
5. User authenticates in the browser and grants consent.
6. Authorization server redirects to the local callback with the authorization code.
7. CLI receives the code and exchanges it for tokens at the token endpoint.
8. Tokens are stored in `~/.orchid/tokens.json` with `0o600` permissions.
9. CLI prints confirmation with user ID and tenant.

## Token Storage

Tokens are stored in `~/.orchid/tokens.json`:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "refresh_token": "rt_secret_refresh_token...",
  "expires_at": "2025-06-01T00:00:00Z",
  "token_type": "Bearer",
  "tenant_key": "my-tenant",
  "user_id": "user-123",
  "scope": "openid profile email"
}
```

### File Permissions

Tokens are written with restricted permissions:

```python
import os, stat
os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600
```

Only the file owner can read or write the token file.

## Logout

```bash
orchid auth logout
```

Deletes `~/.orchid/tokens.json`. Subsequent CLI commands will use `dev_bypass` or prompt for login.

## Status

```bash
orchid auth status
```

Output when authenticated:

```
Status: Authenticated
User: user-123
Tenant: my-tenant
Scopes: openid, profile, email
Issuer: https://auth.example.com
Access token expires: 2025-06-01 00:00 UTC (in 58 minutes)
Refresh token: available
```

Output when not authenticated:

```
Status: Not authenticated
Run 'orchid auth login' to authenticate.
```

## Token Refresh

When an access token expires, the CLI automatically attempts to refresh it:

1. CLI detects a 401 response or pre-emptively checks the `expires_at` time.
2. Sends the refresh token to the token endpoint.
3. Receives a new access token and refresh token (token rotation).
4. Updates `~/.orchid/tokens.json` with the new tokens.

The user doesn't need to re-authenticate unless the refresh token itself expires or is revoked by the server.

## Configuration

OAuth endpoints are configured in `orchid.yml`:

```yaml
auth:
  oidc_issuer: https://auth.example.com
  oidc_client_id: my-cli-app
  oidc_client_secret: ${OIDC_CLIENT_SECRET}
```

Or via environment variables:

```bash
OIDC_ISSUER=https://auth.example.com
OIDC_CLIENT_ID=my-cli-app
```

If the issuer supports OIDC discovery, the CLI auto-discovers authorization and token endpoints from `/.well-known/openid-configuration`.

## Non-OIDC Providers

For providers without OIDC discovery, configure endpoints directly:

```yaml
auth:
  authorization_endpoint: https://auth.example.com/authorize
  token_endpoint: https://auth.example.com/token
  oidc_client_id: my-cli-app
```

## Headless Login (Device Flow)

For environments without a browser:

```bash
orchid auth login --device-flow
```

The device flow:
1. CLI requests a device code from the authorization server.
2. Prints a URL and user code for the user to enter on another device.
3. CLI polls the token endpoint until the user completes authorization.
4. Tokens are stored as usual with proper permissions.
