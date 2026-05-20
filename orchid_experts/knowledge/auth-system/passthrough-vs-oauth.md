<!-- Source: derived from orchid-website/src/content/concepts/mcp.mdx, orchid/AGENTS.md, and codebase analysis -->

# Passthrough vs OAuth

Orchid's MCP server authentication offers two authenticated modes: `passthrough` and `oauth`. Choosing the right mode depends on your deployment's identity architecture.

## Passthrough Auth

Forwards the graph's `OrchidAuthContext` bearer token unchanged to the MCP server.

### How It Works

```
User → API → Graph (OrchidAuthContext with bearer token)
              │
              │ forwards bearer token
              ▼
         MCP Server (validates same token)
```

### When to Use

- The MCP server trusts the same identity provider as the main application.
- Single-identity deployments (one IdP for everything).
- Internal services behind the same auth gateway.
- Simple deployments where authentication is already handled at the API level.

### Advantages

- Simple setup (just `mode: passthrough`).
- No additional token management.
- Works immediately with existing auth infrastructure.

### Limitations

- The MCP server must trust the same IdP.
- No tenant/user-specific tokens — the same token is forwarded.
- The MCP server sees the same identity as the main application.

## OAuth Auth

Performs a full OAuth 2.0 flow with the MCP server's own authorization server.

### How It Works

```
User → API → Graph (OrchidAuthContext)
              │
              │ 1. MCP server returns 401
              │ 2. Discover auth server (RFC 9728 → 8414)
              │ 3. Dynamic Client Registration (RFC 7591)
              │ 4. Authorization code grant with PKCE
              │ 5. Store tokens in OrchidMCPTokenStore
              │ 6. Call MCP tool with MCP-specific access token
              ▼
         MCP Server (validates own token)
```

### When to Use

- The MCP server has its own authorization server (different IdP).
- External services (third-party APIs, SaaS platforms).
- When you need tenant/user-specific tokens for the MCP server.
- Production deployments with separate security domains.

### Advantages

- Full isolation between the main app and MCP server auth.
- Supports MCP servers with different IdPs.
- Per-user tokens enable fine-grained access control at the MCP server level.
- Automatic token refresh and DCR.

### Limitations

- Requires the MCP server's IdP to support OAuth 2.0 with `registration_endpoint` (for DCR).
- More complex setup (but fully automated by the framework).
- Additional latency on first request (discovery + registration + token exchange).

## Decision Guide

```
Is the MCP server in the same security domain?
├── Yes → Does it share the same IdP?
│   ├── Yes → mode: passthrough
│   └── No → mode: oauth
└── No (external/third-party) → mode: oauth

Does the MCP server require per-user tokens?
├── Yes → mode: oauth
└── No → mode: passthrough (or none if unauthenticated)

Do you need fine-grained access control at the MCP server?
├── Yes → mode: oauth
└── No → mode: passthrough
```

## Comparison

| Aspect | Passthrough | OAuth |
|--------|------------|-------|
| Setup complexity | Minimal | Automated (but more steps) |
| Token management | None (forwards existing) | Automatic (token store + refresh) |
| Identity isolation | Shared (same token) | Isolated (per-server tokens) |
| IdP support | Must share IdP with app | Any OAuth 2.0 IdP |
| Per-user tokens | No | Yes |
| External services | Not recommended | Designed for it |
| Latency overhead | None | First request includes discovery + DCR + token exchange |
