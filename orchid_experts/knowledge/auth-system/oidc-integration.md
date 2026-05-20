<!-- Source: derived from orchid-website/src/content/concepts/oauth.mdx, orchid/AGENTS.md, and codebase analysis -->

# OIDC Integration

OpenID Connect (OIDC) is an authentication layer on top of OAuth 2.0. Orchid supports OIDC for identity resolution and single sign-on.

## OIDC in Orchid

### Identity Resolution

The `OrchidIdentityResolver` can validate OIDC-issued JWTs:

```python
class OIDCResolver(OrchidIdentityResolver):
    async def resolve(self, domain, bearer_token):
        # Validate JWT signature, issuer, audience
        claims = await self._validate_jwt(bearer_token)
        return OrchidAuthContext(
            access_token=bearer_token,
            tenant_key=claims.get("tenant_id", "default"),
            user_id=claims["sub"],
        )
```

### OIDC Discovery

OIDC providers expose a `/.well-known/openid-configuration` endpoint that Orchid can auto-discover:

```json
{
  "issuer": "https://auth.example.com",
  "authorization_endpoint": "https://auth.example.com/authorize",
  "token_endpoint": "https://auth.example.com/token",
  "userinfo_endpoint": "https://auth.example.com/userinfo",
  "jwks_uri": "https://auth.example.com/jwks",
  "scopes_supported": ["openid", "profile", "email"],
  "id_token_signing_alg_values_supported": ["RS256"]
}
```

### Standard Claims

OIDC defines standard claims that Orchid uses:

| Claim | Orchid Use |
|-------|-----------|
| `sub` | `user_id` |
| `iss` | Issuer validation |
| `aud` | Audience validation |
| `exp` | Expiry check |
| `email` | User metadata |
| `name` | Display name |
| `preferred_username` | Alternative user_id |

## Frontend Integration

### NextAuth v5

The orchid-frontend package uses NextAuth v5 for OIDC authentication:

```typescript
// NextAuth configuration
export const authOptions = {
  providers: [
    {
      id: "orchid",
      name: "Orchid",
      type: "oidc",
      issuer: process.env.OIDC_ISSUER,
      clientId: process.env.OIDC_CLIENT_ID,
      clientSecret: process.env.OIDC_CLIENT_SECRET,
    },
  ],
};
```

### Token Proxy Pattern

The frontend proxies tokens through the API to avoid exposing them to the browser:

```
Browser → Next.js Server Action → orchid-api → MCP Server
```

This pattern prevents CORS issues and keeps tokens out of client-side JavaScript.

## Configuration

OIDC can be configured in `orchid.yml`:

```yaml
auth:
  oidc_issuer: https://auth.example.com
  oidc_client_id: ${OIDC_CLIENT_ID}
  oidc_client_secret: ${OIDC_CLIENT_SECRET}
```

Or via environment variables:

```bash
OIDC_ISSUER=https://auth.example.com
OIDC_CLIENT_ID=my-client
OIDC_CLIENT_SECRET=my-secret
```

## Auto-Configuration from OIDC Discovery

When `oidc_issuer` is set, Orchid can auto-configure from the OIDC discovery endpoint:

1. Fetch `/.well-known/openid-configuration` from the issuer.
2. Populate authorization, token, and userinfo endpoints.
3. Configure JWT validation (issuer, JWKS URI).

This reduces manual configuration to just the issuer URL + client credentials.

## Best Practices

- Use RS256 or ES256 for JWT signing (avoid HS256 which requires shared secrets).
- Validate all claims: `iss`, `aud`, `exp`, `iat`.
- Use PKCE for public clients (frontend, mobile).
- Store secrets in environment variables, never in YAML.
- Rotate client secrets regularly.
