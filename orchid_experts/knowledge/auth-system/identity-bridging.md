<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/oauth.mdx, and codebase analysis -->

# Identity Bridging

Identity bridging allows connecting identities from different systems through Orchid. The primary mechanism is the `act_as_user` flow and the `/auth/resolve-identity` endpoint.

## /auth/resolve-identity Endpoint

The API endpoint that bridges an upstream token to an Orchid identity:

```
POST /auth/resolve-identity
Authorization: Bearer <upstream-token>
```

Returns:

```json
{
  "user_id": "user-123",
  "tenant_key": "my-tenant",
  "access_token": "orchid-token-for-downstream-use"
}
```

### How It Works

1. Client sends an upstream bearer token to `/auth/resolve-identity`.
2. The API calls `OrchidIdentityResolver.resolve(domain, bearer_token)`.
3. The resolver validates the upstream token and returns an `OrchidAuthContext`.
4. The API returns the Orchid identity to the client.

## act_as_user Flow

The `act_as_user` identity mode in Bloom events impersonates a user:

```yaml
triggers:
  - id: support-ticket-triage
    emits:
      identity:
        mode: act_as_user
        user_id_from: payload.requester.id
```

### How It Works

1. A signal (e.g., webhook) arrives with user information in the payload.
2. The trigger extracts `user_id` from the signal payload using JMESPath.
3. The processor calls `OrchidIdentityResolver.mint_for_user(tenant_key, user_id)`.
4. The resolver returns an `OrchidAuthContext` for the user.
5. The Bloom run executes under the user's identity.

### Probing at Boot

The resolver is probed at boot to ensure it can mint users:

```python
try:
    await resolver.mint_for_user("test", "test-user")
except MintingProbeUnsupportedError:
    raise ConfigError("Resolver cannot mint users")
```

A resolver that can't mint at all gets a deterministic boot-time failure.

## addressed_to_user Flow

Similar to `act_as_user`, but the Bloom run executes under a service account identity tagged with the user's ID:

```yaml
triggers:
  - id: notification-digest
    emits:
      identity:
        mode: addressed_to_user
        service_account: digest-bot
        user_id_from: payload.user.id
```

### How It Works

1. The processor calls `resolve_service_account("digest-bot")`.
2. The resulting auth context is tagged with the user's ID from the signal payload.
3. The Bloom run executes under the service account, but RAG scoping uses the user's ID.

This avoids full impersonation while still enabling user-scoped operations.

## service_account Mode

The simplest identity mode for background jobs:

```yaml
triggers:
  - id: daily-report
    emits:
      identity:
        mode: service_account
        name: report-bot
```

The Bloom run executes under a named service account identity with no user-of-record. Incompatible with `respect_chat_binding: true`.

## Identity Bridge in MCP Gateway

The MCP gateway also uses identity bridging:

1. An MCP host (e.g., Claude Desktop) connects with its own OAuth token.
2. The gateway calls `/auth/resolve-identity` with the MCP host's token.
3. The API returns the Orchid identity for the MCP host.
4. Subsequent MCP tool calls use the Orchid identity for RAG scoping and agent routing.

This allows the MCP gateway to bridge between the MCP host's identity and Orchid's identity, without the MCP host needing to know about Orchid's auth system.
