<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, orchid-website/src/content/concepts/persistence.mdx, and codebase analysis -->

# Persistence

Orchid provides pluggable chat persistence through the `OrchidChatStorage` abstract base class. The library ships with built-in SQLite and PostgreSQL implementations. Consumer projects can implement alternative backends by subclassing the ABC.

## OrchidChatStorage ABC

**File:** `persistence/base.py`

The abstract interface for chat session and message CRUD. All persistence backends implement this contract.

### Lifecycle

- **`init_db()`** — Initialize the database connection and run migrations. Called at application startup.
- **`close()`** — Close the database connection. Called at application shutdown.

### Session Operations

- **`create_chat(tenant_id, user_id, title)`** — Create a new chat session. Returns an `OrchidChatSession` object with a generated UUID.
- **`list_chats(tenant_id, user_id)`** — List all chat sessions for a user, ordered by `updated_at` descending.
- **`get_chat(chat_id)`** — Retrieve a single chat session by ID. Returns `None` if not found.
- **`delete_chat(chat_id)`** — Delete a chat session and all its messages.
- **`update_title(chat_id, title)`** — Update the chat session title and `updated_at` timestamp.
- **`mark_shared(chat_id)`** — Mark a chat session as shared (sets `is_shared = true`).

### Message Operations

- **`add_message(chat_id, role, content, agents_used, metadata)`** — Add a message to a chat session. Also updates the chat's `updated_at` timestamp. Returns an `OrchidChatMessage` object.
- **`get_messages(chat_id, limit, offset)`** — Retrieve messages for a chat session, ordered by `created_at` ascending. Supports pagination via `limit` and `offset`.

## Data Models

### OrchidChatSession

- **`id`** — UUID string.
- **`tenant_id`** — The tenant identifier.
- **`user_id`** — The user identifier.
- **`title`** — Chat session title.
- **`created_at`** — ISO timestamp.
- **`updated_at`** — ISO timestamp.
- **`is_shared`** — Boolean flag for shared chats.

### OrchidChatMessage

- **`id`** — UUID string.
- **`chat_id`** — Parent chat session ID.
- **`role`** — Message role (`user`, `assistant`, `system`).
- **`content`** — Message content.
- **`agents_used`** — List of agent names used in generating this message.
- **`created_at`** — ISO timestamp.
- **`metadata`** — Arbitrary JSON metadata (e.g., `{"origin": "bloom"}` for Bloom-generated messages).

## Built-in SQLite Implementation

**File:** `persistence/sqlite.py`

`OrchidSQLiteChatStorage` uses `aiosqlite` for async SQLite access. It is the default storage backend.

### Configuration

```yaml
storage:
  class: orchid_ai.persistence.sqlite.OrchidSQLiteChatStorage
  dsn: /data/chats.db
```

### Features

- Single-file database (or `:memory:` for tests).
- WAL journal mode for concurrent read access.
- Foreign keys enabled.
- Automatic migration execution on `init_db()`.

### Migration Tracking

Uses a `_migrations` table to track applied migrations. The `SQLiteMigrationRunner` class manages:

- Creating the migrations table if it doesn't exist.
- Checking which migrations have been applied.
- Recording new migrations after execution.
- Supporting rollback via `remove_version()`.

## PostgreSQL Storage Plugin

`OrchidPostgresChatStorage` is provided by the `orchid-storage-postgres` plugin package.  Install it alongside `orchid-ai`:

```bash
pip install orchid-storage-postgres
```

### Configuration

```yaml
storage:
  class: orchid_storage_postgres.OrchidPostgresChatStorage
  dsn: postgresql+asyncpg://user:pass@localhost:5432/orchid
```

### Features

- Full ACID compliance.
- Connection pooling via `asyncpg`.
- Automatic migration execution on `init_db()`.
- Suitable for multi-replica deployments.
- Includes PostgreSQL checkpointer (bundled) and visibility fragment.

## Migration System

**File:** `persistence/migrations/`

Orchid uses a unified migration system that covers chat, MCP, and gateway-state tables in a single migration run.

### Migration Runner

The `OrchidMigrationRunner` ABC defines:

- **`dialect`** — The SQL dialect (`sqlite` or `postgres`).
- **`migrations_package`** — Dotted import path to the migration SQL files.
- **`ensure_migrations_table(conn)`** — Create the `_migrations` tracking table.
- **`get_applied_versions(conn)`** — Return set of already applied migration versions.
- **`record_version(conn, version, description)`** — Record a new applied migration.
- **`remove_version(conn, version)`** — Remove a migration record (for rollback).

### Migration Files

Migration files are SQL scripts stored in a package directory. They are named `v{NNN}_{description}.sql` (e.g., `v001_initial_schema.sql`). The runner applies them in order, skipping already-applied versions.

### Custom Migrations

Consumer projects can add custom migrations by specifying `extra_migrations_package` when constructing the storage backend:

```python
storage = OrchidSQLiteChatStorage(
    dsn="/data/chats.db",
    extra_migrations_package="myproject.migrations",
)
```

The extra migrations are applied after the built-in ones.

## Custom Storage Backends

To implement a custom storage backend:

1. Subclass `OrchidChatStorage`.
2. Implement all abstract methods.
3. Reference it via dotted import path in `orchid.yml`:

```yaml
storage:
  class: myproject.storage.MyChatStorage
  dsn: my-connection-string
```

The constructor must accept `dsn` and `extra_migrations_package` keyword arguments.

## Important Notes

- **Never persist augmented prompts.** Save the original user message to chat history, NOT the version with file content prepended.
- **Bloom messages carry metadata.** Messages generated by Bloom runs include `metadata.origin: "bloom"` so they can be distinguished from user-initiated messages.
- **Shared chats.** The `mark_shared()` method sets `is_shared = true`, enabling chat sharing across users within the same tenant.
