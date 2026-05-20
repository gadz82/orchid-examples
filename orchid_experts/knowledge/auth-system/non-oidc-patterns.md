<!-- Source: derived from orchid-website/src/content/concepts/oauth.mdx, orchid/AGENTS.md, and codebase analysis -->

# Non-OIDC Patterns

Not all deployments use OpenID Connect (OIDC). Orchid supports various non-OIDC authentication patterns for different integration scenarios.

## Bearer Token Authentication

The simplest pattern: any bearer token is accepted. Used in demos and development:

```python
class TrivialResolver(OrchidIdentityResolver):
    async def resolve(self, domain, bearer_token):
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key="demo",
            user_id="bearer-user",
        )
```

### When to Use

- Local development and demos.
- Testing without an identity provider.
- Prototyping.

### Limitations

- No real authentication (any token works).
- No multi-tenancy support.
- Same identity for all requests.

## API Key Authentication

Use API keys instead of OAuth tokens:

```python
class APIKeyResolver(OrchidIdentityResolver):
    def __init__(self, api_keys: dict[str, str]):
        self._api_keys = api_keys  # key → user_id mapping

    async def resolve(self, domain, bearer_token):
        key = bearer_token.replace("Bearer ", "")
        user_id = self._api_keys.get(key)
        if not user_id:
            raise ValueError("Invalid API key")
        return OrchidAuthContext(
            access_token=key,
            tenant_key=domain,
            user_id=user_id,
        )
```

### When to Use

- Internal services without OAuth infrastructure.
- CLI tools.
- Machine-to-machine communication.

### Limitations

- No standard token lifecycle (no expiry, no refresh).
- Key rotation requires manual intervention.
- Less secure than OAuth (no PKCE, no JWT validation).

## JWT-Based Authentication

Validate JWTs without OIDC discovery:

```python
class JWTResolver(OrchidIdentityResolver):
    async def resolve(self, domain, bearer_token):
        token = bearer_token.replace("Bearer ", "")
        # Decode without verification (for HS256 shared secrets)
        claims = jwt.decode(token, self._shared_secret, algorithms=["HS256"])
        return OrchidAuthContext(
            access_token=token,
            tenant_key=claims.get("tenant", "default"),
            user_id=claims["sub"],
        )
```

### When to Use

- Internal services with shared secrets.
- When you control both token issuer and validator.
- HMAC-based JWT signing (HS256, HS384, HS512).

### Limitations

- Shared secret management.
- No key rotation without re-deployment.
- Less secure than asymmetric JWT (RS256, ES256).

## Custom Auth Provider Integration

Integrate with any authentication provider by implementing `OrchidIdentityResolver`:

```python
class CustomAuthResolver(OrchidIdentityResolver):
    async def resolve(self, domain, bearer_token):
        # Call your auth provider's validation endpoint
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://my-auth.example.com/validate",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
            data = response.json()
            return OrchidAuthContext(
                access_token=bearer_token,
                tenant_key=data["tenant"],
                user_id=data["user_id"],
            )
```

### When to Use

- Proprietary auth systems.
- Legacy auth infrastructure.
- SAML-based systems.

## dev_bypass Mode

For local development, `dev_bypass: true` skips authentication entirely:

```yaml
auth:
  dev_bypass: true
```

When enabled, all requests are authenticated as a synthetic user without any token validation.

### When to Use

- Local development only.
- Never in production.
- Quick testing without any auth setup.

## Best Practices

- **Validate tokens** — Even in non-OIDC patterns, validate tokens (expiry, signature, audience).
- **Use environment variables for secrets** — Never hardcode API keys or shared secrets.
- **Implement token rotation** — Plan for rotating API keys and shared secrets.
- **Add audit logging** — Log authentication events for security monitoring.
- **Don't use `dev_bypass: true` in production** — It disables all authentication.
