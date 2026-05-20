<!-- Source: derived from orchid-website/src/content/concepts/mcp.mdx, orchid/AGENTS.md, and codebase analysis -->

# Auth Modes

MCP servers in Orchid support three authentication modes, configured via `auth.mode` in `OrchidMCPServerConfig`. The YAML carries ONLY the mode — no `client_id`, `client_secret`, or endpoints.

## Mode: none (Default)

No authentication headers sent. Use for local/unauthenticated MCP servers.

```yaml
mcp_servers:
  - name: local-tools
    url: http://localhost:3001/mcp
    tools: "*"
    auth:
      mode: none
```

### When to Use
- Local development servers.
- Internal servers without authentication.
- Demos and prototypes.

### Capability Warming
Servers with `auth.mode: none` are warmed at process startup. Capabilities are cached for the process lifetime.

## Mode: passthrough

Forwards the graph's `OrchidAuthContext` bearer token unchanged.

```yaml
mcp_servers:
  - name: internal-api
    url: ${INTERNAL_MCP_URL}
    tools: "*"
    auth:
      mode: passthrough
```

### How It Works

1. The graph's `OrchidAuthContext` token is obtained ONCE at the API entry point.
2. When calling MCP tools on this server, the token is forwarded as a bearer header.
3. The MCP server validates the token using the same identity provider.

### When to Use
- The MCP server trusts the same identity provider as the main application.
- Single-identity deployments.
- Internal services behind the same auth gateway.

### Capability Warming
Servers with `auth.mode: passthrough` are warmed once per `(tenant_key, user_id)` at user-session start. Capabilities are cached for the session lifetime.

## Mode: oauth

Per-user OAuth 2.0 flow with the MCP server's authorization server. Follows the **MCP 2025-03-26 authorization spec**.

```yaml
mcp_servers:
  - name: external-crm
    url: ${CRM_MCP_URL}
    tools: "*"
    auth:
      mode: oauth
```

### How It Works

1. On the first 401 response from the MCP server, the framework consumes the `WWW-Authenticate: Bearer resource_metadata="…"` header (RFC 9728).
2. Fetches the authorization server metadata (RFC 8414) from the resource metadata.
3. Dynamically registers a client (RFC 7591) via the `registration_endpoint`.
4. Persists the resulting endpoints + DCR credentials to `OrchidMCPClientRegistrationStore`.
5. Per-user tokens land in `OrchidMCPTokenStore` and are refreshed against the discovered token endpoint automatically.

### Prerequisites

The authorization server MUST advertise `registration_endpoint` in its RFC 8414 metadata. If it doesn't, discovery fails with a clear error.

### Manual Registration

For IdPs without DCR support, seed `OrchidMCPClientRegistrationStore` manually with the relevant endpoints + client credentials before first use.

### Capability Warming
Servers with `auth.mode: oauth` are warmed once per `(tenant_key, user_id)` at user-session start (after token acquisition). Capabilities are cached for the session lifetime.

## Decision Tree

```
Does the MCP server require authentication?
├── No → mode: none
└── Yes
    ├── Does the server trust the same identity provider?
    │   └── Yes → mode: passthrough
    └── No
        └── Does the server support OAuth 2.0 with DCR?
            ├── Yes → mode: oauth
            └── No → Seed OrchidMCPClientRegistrationStore manually, then use mode: oauth
```

## Token Stores

| Store | Purpose |
|-------|---------|
| `OrchidMCPTokenStore` | Per-user outbound OAuth token persistence. |
| `OrchidMCPClientRegistrationStore` | Per-server discovered endpoints + DCR credentials. |

Both are ABCs in `core/mcp.py` with built-in SQLite and PostgreSQL implementations.
