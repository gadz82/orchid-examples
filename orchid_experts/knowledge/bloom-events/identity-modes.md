<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx, orchid/README.md, and codebase analysis -->

# Identity Modes

Bloom runs execute under a synthesized `OrchidAuthContext`. The identity mode determines how this context is constructed. Three modes are available as a discriminated union.

## service_account

The Bloom run executes under a named service identity with no user-of-record.

```yaml
emits:
  identity:
    mode: service_account
    name: digest-bot
```

### How It Works

1. Processor calls `OrchidIdentityResolver.resolve_service_account(name)`.
2. Returns an `OrchidAuthContext` for the service account.
3. RAG scoping uses the tenant but not a specific user.

### Use Cases

- Scheduled digests and reports.
- System-level background tasks.
- Operations that don't need user-scoped data.

### Limitations

- Incompatible with `respect_chat_binding: true` (no user-of-record to bind to).
- Cannot access user-private RAG data.
- Visibility defaults to `admin`.

## addressed_to_user

The Bloom run executes under a service account but is tagged with a user ID from the signal payload.

```yaml
emits:
  identity:
    mode: addressed_to_user
    service_account: support-bot
    user_id_from: payload.requester.id
```

### How It Works

1. Processor calls `resolve_service_account(service_account)`.
2. Extracts `user_id` from the signal payload using JMESPath (`payload.requester.id`).
3. The resulting auth context is tagged with the user's ID.
4. RAG scoping uses the user's ID, but auth is service account.

### Use Cases

- User-scoped operations without full impersonation.
- Notifications and alerts addressed to specific users.
- Operations where user context is needed but trust is limited.

### Advantages

- Safer than `act_as_user` (no full impersonation).
- User-scoped RAG works correctly.
- Compatible with `respect_chat_binding: true`.

## act_as_user

Full user impersonation. The Bloom run executes as the user.

```yaml
emits:
  identity:
    mode: act_as_user
    user_id_from: payload.user.id
```

### How It Works

1. Processor extracts `user_id` from signal payload using JMESPath.
2. Calls `OrchidIdentityResolver.mint_for_user(tenant_key, user_id)`.
3. The resolver returns an `OrchidAuthContext` for the user.
4. The Bloom run executes with full user permissions.

### Use Cases

- User-triggered workflows.
- Operations that need full user identity.
- Chat binding where the user should "own" the response.

### Requirements

- The resolver must support `mint_for_user()`.
- Probed at boot — a resolver that can't mint gets a boot-time failure.
- Most sensitive mode — use only when necessary.

### Compatibility Matrix

| Identity Mode | respect_chat_binding | Visibility Default |
|--------------|---------------------|-------------------|
| `service_account` | ❌ Incompatible | `admin` |
| `addressed_to_user` | ✅ Supported | `addressed` |
| `act_as_user` | ✅ Supported | `actor` |

## JMESPath Extraction

The `user_id_from` field uses JMESPath to extract values from the signal envelope:

```
payload.requester.id        → signal.payload.requester.id
payload.user.sub            → signal.payload.user.sub
metadata.source.user        → signal.metadata.source.user
```

Invalid JMESPath expressions fail at trigger registration time (boot-time error).
