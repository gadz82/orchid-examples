<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, and codebase analysis -->

# Token Stores

Orchid uses multiple token store ABCs for different OAuth token types. Each store has built-in SQLite and PostgreSQL implementations.

## Token Store Types

| Store | Purpose | Scope |
|-------|---------|-------|
| `OrchidMCPTokenStore` | Per-user outbound OAuth tokens for MCP servers. | Per `(server, user)` |
| `OrchidMCPClientRegistrationStore` | Per-server DCR credentials + discovered endpoints. | Per server |
| `OrchidMCPGatewayTokenStore` | Inbound issued access + refresh tokens for gateway clients. | Per `(client, user)` |
| `OrchidMCPGatewayAuthCodeStore` | Inbound in-flight authorization codes. | Per code |
| `OrchidMCPGatewayClientStore` | Inbound DCR client registrations for the gateway. | Per client |

## OrchidMCPTokenStore

Stores per-user tokens for outbound MCP server OAuth:

```python
class OrchidMCPTokenStore(ABC):
    async def store_token(self, server_name: str, user_id: str, 
                          tenant_key: str, token: OAuthToken) -> None: ...
    async def get_token(self, server_name: str, user_id: str, 
                        tenant_key: str) -> OAuthToken | None: ...
    async def delete_token(self, server_name: str, user_id: str, 
                           tenant_key: str) -> None: ...
```

### OAuthToken

```python
@dataclass
class OAuthToken:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    token_type: str = "Bearer"
    scope: str = ""
```

## OrchidMCPClientRegistrationStore

Stores per-server DCR credentials:

```python
class OrchidMCPClientRegistrationStore(ABC):
    async def store_registration(self, server_name: str, 
                                  registration: ClientRegistration) -> None: ...
    async def get_registration(self, server_name: str) -> ClientRegistration | None: ...
    async def delete_registration(self, server_name: str) -> None: ...
```

### ClientRegistration

```python
@dataclass
class ClientRegistration:
    client_id: str
    client_secret: str
    token_endpoint: str
    authorization_endpoint: str
    registration_client_uri: str | None = None
```

## Gateway Token Stores

### OrchidMCPGatewayTokenStore

Stores tokens issued by the MCP gateway to external MCP hosts:

```python
class OrchidMCPGatewayTokenStore(ABC):
    async def store(self, token: OrchidMCPGatewayToken) -> None: ...
    async def get_by_access(self, access_token: str) -> OrchidMCPGatewayToken | None: ...
    async def get_by_refresh(self, refresh_token: str) -> OrchidMCPGatewayToken | None: ...
    async def revoke(self, token_id: str) -> None: ...
```

### OrchidMCPGatewayToken

```python
@dataclass
class OrchidMCPGatewayToken:
    id: str
    client_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime
    idp_access_token: str | None  # Upstream IdP access token
    idp_refresh_token: str | None  # Upstream IdP refresh token
    idp_expires_at: datetime | None
    tenant_key: str
    user_id: str | None
```

The `idp_*` fields enable the refresh path to swap upstream tokens.

## Implementation

Built-in implementations use the shared chat database:

- **SQLite** — `OrchidSQLiteMCPTokenStore`, `OrchidSQLiteMCPClientRegistrationStore`, etc.
- **PostgreSQL** — `OrchidPostgresMCPTokenStore`, `OrchidPostgresMCPClientRegistrationStore`, etc.

All token stores share the same database as chat storage, using the unified `v001_initial_schema` migration.

## Factory Functions

```python
from orchid_ai.persistence.mcp_token_factory import build_mcp_token_store

token_store = build_mcp_token_store(dsn="sqlite:///data/chats.db")
```

The factory auto-detects the database type from the DSN.
