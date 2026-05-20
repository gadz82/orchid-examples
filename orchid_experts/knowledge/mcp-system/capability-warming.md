<!-- Source: derived from orchid/AGENTS.md, orchid-mcp/AGENTS.md, and codebase analysis -->

# Capability Warming

Capability warming is the process of proactively discovering MCP server capabilities (tools, prompts, resources) before they are needed by agents. This avoids discovery RPCs on the first agentic turn, reducing latency.

## OrchidSessionWarmer

The `OrchidSessionWarmer` drives `OrchidMCPClient.warm_cache(auth)` at the right lifecycle boundaries:

```python
from orchid_ai.mcp.warmer import OrchidSessionWarmer

warmer = OrchidSessionWarmer(mcp_clients, auth_registry)
await warmer.warm_startup()  # Warm unauthenticated servers
await warmer.warm_user(auth)  # Warm per-user servers
```

## Warming Lifecycle

### Process Startup (Unauthenticated Servers)

Servers with `auth.mode: none` are warmed at process startup:

- Called from the `orchid-api` lifespan / `orchid-cli` bootstrap.
- `Orchid.warm_unauthenticated_capabilities()` iterates all `auth.mode: none` servers.
- Capabilities are cached for the process lifetime.

### User-Session Start (Authenticated Servers)

Servers with `auth.mode: passthrough` or `oauth` are warmed once per `(tenant_key, user_id)`:

- Called from `POST /session/warm` (from the frontend).
- A fire-and-forget backstop in `get_auth_context()` ensures warming happens even if the frontend doesn't call `/session/warm`.
- Capabilities are cached for the session lifetime.

## Cache Lifetime

| Auth Mode | Warm Trigger | Cache Lifetime |
|-----------|-------------|----------------|
| `none` | Process startup | Process lifetime |
| `passthrough` | User-session start | Session lifetime |
| `oauth` | User-session start (after token acquisition) | Session lifetime |

## Cache Invalidation

Capabilities can be invalidated:

```python
# Invalidate a specific server's cache
await mcp_client.invalidate_cache()

# Invalidate all caches for a user
await session_warmer.invalidate_user(auth)
```

### When to Invalidate

- Server deployment (new tools added).
- Auth token rotation.
- Server configuration changes.

## Hot Path

Once the cache is populated, the per-request hot path (`MCPDispatcher.render_capabilities()`) stops issuing discovery RPCs. This means:

- The first agentic turn after warming is fast (no discovery delay).
- Capabilities are read from memory, not from the MCP server.
- Tool lists are consistent within a session.

## Without Warming

Without proactive warming, the first agentic turn includes discovery RPCs:

1. Agent begins processing a query.
2. `MCPDispatcher` needs tool descriptions.
3. Calls `list_tools()` on each MCP server.
4. Each call adds 50–500ms of latency.
5. Results are cached for subsequent turns.

With warming, step 3 happens before the user's query, so the first turn has no discovery delay.

## Configuration

No YAML configuration needed. Warming is automatic:

- Process-startup warming: handled by `orchid-api` lifespan / `orchid-cli` bootstrap.
- User-session warming: handled by `POST /session/warm` endpoint.

The `OrchidMCPServerConfig.cache_ttl` YAML field is rejected (`extra="forbid"`). Cache lifetime is determined by the warming lifecycle, not by configuration.
