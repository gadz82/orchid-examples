<!-- Source: derived from orchid-website/src/content/best-practices.mdx and codebase analysis -->

# Storage Strategy

Guidelines for choosing and configuring chat persistence and token storage in production.

## PostgreSQL vs SQLite

| Aspect | PostgreSQL | SQLite |
|--------|-----------|--------|
| Concurrency | Excellent (MVCC) | Limited (single-writer) |
| Replication | Built-in (streaming, logical) | Not supported |
| Multi-replica | Yes (horizontal scaling) | No (single-file) |
| Setup | Requires server | Zero-infra |
| Performance | High (connection pooling) | Good (single-process) |
| Backups | pg_dump, WAL archiving | File copy |
| Best For | Production | Dev, demos, single-user |

## Production Storage

### PostgreSQL Configuration

```yaml
storage:
  class: orchid_ai.persistence.postgres.OrchidPostgresChatStorage
  dsn: postgresql+asyncpg://orchid:${DB_PASSWORD}@postgres:5432/orchid
```

### Connection Pooling

PostgreSQL deployments should use connection pooling:

```yaml
dsn: postgresql+asyncpg://orchid:pass@pgbouncer:6432/orchid
```

PgBouncer sits between the API and PostgreSQL, managing connection pools.

### Migrations

Migrations run automatically on `init_db()`:
- Always test migrations in staging before production.
- Back up the database before applying migrations.
- The unified `v001_initial_schema` migration covers chat, MCP tokens, and gateway state.

## Custom Storage Backends

Implement `OrchidChatStorage` for alternative databases:

```python
class MongoChatStorage(OrchidChatStorage):
    async def init_db(self) -> None:
        self._client = AsyncIOMotorClient(self._dsn)

    async def create_chat(self, tenant_id, user_id, title):
        doc = {"tenant_id": tenant_id, "user_id": user_id, "title": title}
        result = await self._db.chats.insert_one(doc)
        return OrchidChatSession(id=str(result.inserted_id), ...)
```

```yaml
storage:
  class: myapp.storage.MongoChatStorage
  dsn: mongodb://localhost:27017/
```

## Backup Strategy

- **SQLite** — Copy the `.db` file while the API is stopped.
- **PostgreSQL** — Use `pg_dump` or WAL archiving for point-in-time recovery.
- **Qdrant** — Use Qdrant snapshots for vector data.

## Data Retention

- Chat history: Retain based on business needs (30-90 days typical).
- MCP tokens: Clean up expired tokens periodically.
- Bloom job runs: Archive or delete after a retention period.
- RAG cache: TTL-based auto-expiry (no manual cleanup needed).
