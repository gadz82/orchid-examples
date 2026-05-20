<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, orchid-website/src/content/concepts/oauth.mdx, and codebase analysis -->

# Identity Resolution

Identity resolution in Orchid is the process of converting a bearer token (from an HTTP request) into an `OrchidAuthContext` that the graph uses for authorization, RAG scoping, and MCP tool calls.

## OrchidIdentityResolver ABC

**File:** `orchid_ai/core/identity.py`

```python
class OrchidIdentityResolver(ABC):
    async def resolve(self, domain: str, bearer_token: str) -> OrchidAuthContext: ...
    async def resolve_service_account(self, name: str) -> OrchidAuthContext: ...
    async def mint_for_user(self, tenant_key: str, user_id: str) -> OrchidAuthContext: ...
```

### resolve()

Validates a bearer token and returns an `OrchidAuthContext`. Called on every API request.

```python
auth_context = await resolver.resolve(domain="my-tenant", bearer_token="Bearer xyz...")
```

### resolve_service_account()

Resolves a named service account identity. Used by Bloom `service_account` identity mode.

```python
auth = await resolver.resolve_service_account(name="digest-bot")
```

Raises `OrchidServiceAccountUnknownError` if the service account name is not recognized.

### mint_for_user()

Mints a new auth context for a known user. Used by Bloom `act_as_user` identity mode.

```python
auth = await resolver.mint_for_user(tenant_key="my-tenant", user_id="user-123")
```

Raises `OrchidIdentityNotMintableError` if the user is not seeded. The resolver is probed at boot — a resolver that can't mint at all gets a deterministic boot-time failure.

## OrchidAuthContext

**File:** `orchid_ai/core/state.py`

```python
@dataclass
class OrchidAuthContext:
    access_token: str
    tenant_key: str
    user_id: str
    bearer_header: str = ""
```

- **`access_token`** — The resolved access token.
- **`tenant_key`** — Tenant identifier (defaults to `"default"` if null).
- **`user_id`** — Authenticated user identifier.
- **`bearer_header`** — Original bearer token for passthrough auth.

## Double Duty

The resolver does double-duty:
1. **Per-request bearer validation** — Validates tokens on every API request.
2. **Identity bridge** — The `/auth/resolve-identity` endpoint uses the resolver to bridge from upstream tokens to Orchid identities.

## Trivial Resolver Pattern

For demos and development, a trivial resolver accepts any bearer token:

```python
class TrivialResolver(OrchidIdentityResolver):
    async def resolve(self, domain, bearer_token):
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key="demo",
            user_id="bearer-user",
        )

    async def resolve_service_account(self, name):
        raise OrchidServiceAccountUnknownError(name)

    async def mint_for_user(self, tenant_key, user_id):
        raise OrchidIdentityNotMintableError(tenant_key, user_id)
```

## Production Resolver

For production, the resolver validates against an identity provider:

```python
class OIDCResolver(OrchidIdentityResolver):
    async def resolve(self, domain, bearer_token):
        claims = await self._validate_jwt(bearer_token)
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key=claims.get("tenant_id", "default"),
            user_id=claims["sub"],
        )
```

## Configuration

The resolver class is specified in `orchid.yml`:

```yaml
auth:
  dev_bypass: false
  identity_resolver_class: myproject.identity.MyResolver
```

Resolved via `importlib` at startup.
