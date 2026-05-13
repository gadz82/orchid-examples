# MCP Auth Example — Authentication Patterns

Demonstrates all **three MCP authentication modes** supported by Orchid: `none` (no auth), `passthrough` (bearer token forwarding), and `oauth` (per-user OAuth 2.0 flow with dynamic client registration).

## What It Demonstrates

- **MCP `none` mode** — Local/unauthenticated MCP servers with no auth headers
- **MCP `passthrough` mode** — Forwards the graph's `OrchidAuthContext` bearer token unchanged
- **MCP `oauth` mode** — Per-user OAuth 2.0 flow with RFC 9728 / RFC 8414 / RFC 7591 DCR
- **Dynamic client registration** — No pre-registered OAuth client required
- **Token storage** — Per-user OAuth tokens persisted in `OrchidMCPTokenStore`
- **Capability caching** — MCP server capabilities discovered once and cached per session

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Auth modes | `none`, `passthrough`, `oauth` (all three demonstrated) |
| OAuth flow | Authorization Code + PKCE with dynamic client registration |
| Token storage | `OrchidSQLiteMCPTokenStore` (or Postgres in production) |
| MCP servers | 3 servers: local (none), internal (passthrough), external CRM (oauth) |
| Agent config | YAML-only, no custom Python required |
| Discovery | RFC 8414 OAuth discovery + RFC 7591 DCR |

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  MCP Client  │────▶│  orchid-api  │────▶│  Local MCP   │
│  (Claude)    │     │  (gateway)   │     │  (no auth)   │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Internal MCP│
                     │  (passthrough│
                     │   bearer)    │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  External CRM│
                     │  (OAuth 2.0) │
                     └──────────────┘
```

## Prerequisites

- Three MCP servers running:
  - **Local server** (no auth) at `$LOCAL_MCP_URL`
  - **Internal server** (bearer passthrough) at `$INTERNAL_MCP_URL`
  - **External CRM server** (OAuth) at `$CRM_MCP_URL`
- Ollama running with `ollama pull llama3.2`
- Python 3.11+ with `orchid-ai` and `orchid-api` installed
- `API_BASE_URL` set for OAuth redirect URI discovery

## Usage

### Environment Variables

```bash
export LOCAL_MCP_URL=http://localhost:8001/mcp
export INTERNAL_MCP_URL=http://localhost:8002/mcp
export CRM_MCP_URL=https://crm.example.com/mcp
export API_BASE_URL=http://localhost:8000
```

### Via CLI

```bash
# Install dependencies (from repo root)
pip install -e orchid -e orchid-cli

# Authenticate (required for OAuth MCP servers)
orchid auth login --config examples/mcp-auth/orchid.yml

# Check auth status
orchid auth status --config examples/mcp-auth/orchid.yml

# Check MCP server OAuth status
orchid mcp status --config examples/mcp-auth/orchid.yml

# Interactive session
orchid chat interactive --config examples/mcp-auth/orchid.yml
```

### Via API

```bash
ORCHID_CONFIG=examples/mcp-auth/orchid.yml \
  uvicorn orchid_api.main:app --port 8000

# List MCP servers and auth status
curl http://localhost:8000/mcp/auth/servers

# Authorize OAuth server (opens browser)
curl "http://localhost:8000/mcp/auth/servers/crm-server/authorize"

# Revoke OAuth token
curl -X DELETE http://localhost:8000/mcp/auth/servers/crm-server/token
```

## File Layout

```
examples/mcp-auth/
├── orchid.yml              # Runtime config (LLM, storage)
├── agents.yaml             # Three agents + MCP server configs
└── __init__.py
```

## Configuration Walkthrough

### Agent with No Auth

```yaml
agents:
  local-tools:
    description: Agent with local MCP server (no auth)
    mcp_servers:
      - name: local-server
        type: local
        url: "${LOCAL_MCP_URL}"
        tools: "*"
        # auth omitted → defaults to mode: none
```

### Agent with Passthrough Auth

```yaml
agents:
  internal-api:
    description: Agent accessing internal API
    mcp_servers:
      - name: internal-platform
        type: remote
        url: "${INTERNAL_MCP_URL}"
        tools: "*"
        auth:
          mode: passthrough
```

The graph's `OrchidAuthContext` bearer token (from the API entry point) is forwarded unchanged.

### Agent with OAuth Auth

```yaml
agents:
  crm-access:
    description: Agent with external CRM (OAuth)
    mcp_servers:
      - name: crm-server
        type: remote
        url: "${CRM_MCP_URL}"
        tools: "*"
        auth:
          mode: oauth
```

On first 401, the framework:
1. Runs RFC 9728 resource metadata discovery
2. Fetches RFC 8414 authorization server metadata
3. Performs RFC 7591 dynamic client registration
4. Executes Authorization Code + PKCE flow
5. Stores tokens in `OrchidMCPTokenStore`
6. Auto-refreshes tokens on expiry

## OAuth Flow Details

### Discovery Phase

```
GET ${CRM_MCP_URL}/.well-known/oauth-protected-resource
→ { "authorization_servers": ["https://auth.crm.example.com"] }

GET https://auth.crm.example.com/.well-known/oauth-authorization-server
→ { "authorization_endpoint", "token_endpoint", "registration_endpoint" }
```

### Dynamic Client Registration

```
POST https://auth.crm.example.com/register
Content-Type: application/json

{
  "redirect_uris": ["${API_BASE_URL}/mcp/auth/callback"],
  "grant_types": ["authorization_code", "refresh_token"],
  "token_endpoint_auth_method": "client_secret_basic"
}

→ {
  "client_id": "...",
  "client_secret": "...",
  "client_id_issued_at": 1234567890
}
```

Credentials stored in `OrchidMCPClientRegistrationStore` per server.

### Authorization Flow

1. User clicks "Authorize" in UI
2. Gateway generates PKCE code verifier + challenge
3. Redirect to IdP authorization endpoint
4. User authenticates and consents
5. IdP redirects back with `code` + `state`
6. Gateway exchanges code for tokens (includes `client_secret`)
7. Tokens stored in `OrchidMCPTokenStore` keyed by `(tenant_key, user_id, server_name)`
8. Access token used for subsequent MCP calls
9. Refresh token used automatically on expiry

## MCP Endpoints

When OAuth mode is configured:

| Endpoint | Purpose |
|----------|---------|
| `GET /mcp/auth/servers` | List OAuth servers + user auth status |
| `GET /mcp/auth/servers/{name}/authorize` | Generate OAuth URL (PKCE) |
| `GET /mcp/auth/callback` | OAuth IdP redirect callback |
| `DELETE /mcp/auth/servers/{name}/token` | Revoke stored token |

## Token Storage

OAuth tokens are stored per-user, per-server:

```python
# Schema (simplified)
CREATE TABLE orchid_mcp_oauth_tokens (
    tenant_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    server_name TEXT NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP,
    scopes TEXT,
    PRIMARY KEY (tenant_key, user_id, server_name)
);
```

## Contrast with Other Examples

| Example | Auth Modes | OAuth | Custom Code |
|---------|-----------|-------|-------------|
| basketball | Dev bypass | No | SQLite storage |
| helpdesk | Dev bypass | No | Event workflow |
| **mcp-auth** | **All three** | **Yes (full flow)** | **None (YAML-only)** |
| restaurant | Dev bypass | No | Custom agent |

## Security Considerations

### Production Deployment

1. **Never use `dev_bypass: true`** — wire a real `OrchidIdentityResolver`
2. **Use HTTPS** — OAuth tokens must not traverse unencrypted connections
3. **Set `API_BASE_URL`** — OAuth redirect URI must match exactly
4. **Token rotation** — Refresh tokens are used automatically; access tokens have TTL
5. **Token revocation** — Users can revoke per-server tokens via UI or API

### Multi-Replica Deployments

For multi-replica `orchid-api` deployments:
- Use `OrchidPostgresMCPTokenStore` instead of SQLite
- Set `MCP_TOKEN_STORE_DSN` to shared Postgres connection
- All replicas share the same token database

## Troubleshooting

### 401 on MCP Tool Calls

- Check `orchid mcp status` — OAuth token may be expired
- Run `orchid auth login` to refresh
- Verify `API_BASE_URL` matches OAuth redirect URI

### OAuth Redirect Mismatch

- Ensure `API_BASE_URL` is set in orchid-api environment
- The callback URL is `${API_BASE_URL}/mcp/auth/callback`
- Register this exact URL with your IdP (or use wildcard if supported)

### DCR Returns 405

- Some IdPs disable dynamic client registration
- Set `ORCHID_MCP_OAUTH_CLIENT_REGISTRATION_ENABLED=false`
- Pre-register client out-of-band and provide credentials via env vars

## Next Steps

After exploring mcp-auth:
- **orchid-mcp** — MCP gateway for Claude Desktop/Cursor
- **helpdesk** — Event-driven workflows
- **wiki** — Advanced RAG with hybrid retrieval
