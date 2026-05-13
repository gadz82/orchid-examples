# Custom-storage example

Demonstrates how to plug an alternative chat persistence backend into
Orchid by subclassing `OrchidChatStorage`. Ships a JSON-file
implementation suitable for demos, single-process embedded apps, and
offline notebooks.

## What you'll learn

- The full `OrchidChatStorage` ABC contract — every abstract method
  and how it's invoked by the API / CLI.
- How `build_chat_storage()` resolves the YAML `storage.class` field
  to a concrete class via `importlib`, then constructs it with
  `dsn=` and `extra_migrations_package=` kwargs.
- Two contract requirements integrators frequently miss:
  - `init_db()` runs once at startup and is the right place for
    schema bootstrap. Don't put I/O in `__init__`.
  - Both `dsn=` and `extra_migrations_package=` constructor kwargs
    are mandatory, even when migrations are ignored — the factory
    passes them unconditionally.

## Files

```
examples/custom-storage/
├── README.md
├── __init__.py
├── orchid.yml             # Wires storage.class to OrchidJSONChatStorage
├── agents.yaml            # One-agent echo demo so chats actually persist
└── storage/
    ├── __init__.py
    └── json_file.py       # The OrchidJSONChatStorage implementation
```

## Backend behaviour

`OrchidJSONChatStorage` keeps the entire chat store in a single JSON
file:

```json
{
  "sessions": {
    "<chat_id>": { "id": "...", "tenant_id": "...", "user_id": "...", ... }
  },
  "messages": {
    "<chat_id>": [ { "id": "...", "role": "user", "content": "...", ... } ]
  }
}
```

Concurrency: an `asyncio.Lock` serialises writes within a single
process. Cross-process safety is **not provided** — running two API
workers against the same file is unsupported. For multi-process
deployments, use the built-in PostgreSQL or SQLite backends.

Atomicity: writes go to a sibling `.tmp` file and are renamed into
place, so a crash mid-write leaves either the previous good state or
the new one — never a partial document.

## Running

```bash
# Validate the YAML loads
orchid config validate examples/custom-storage/agents.yaml

# Run the API and let chat traffic populate the JSON store
ORCHID_CONFIG=examples/custom-storage/orchid.yml \
  uvicorn orchid_api.main:app --port 8000

# Or use the CLI without spinning up the server
orchid chat send "hello world" --config examples/custom-storage/orchid.yml
cat /data/custom_storage_chats.json | jq .
```

## Adapting the backend

Common variants and how to implement them:

| Backend | Key changes |
|---|---|
| Redis | Use `redis.asyncio`; map sessions to a hash keyed by chat_id, messages to a list per chat_id. Wire `init_db()` to ensure indexes/streams exist. |
| MongoDB | Use `motor`; one collection per session/message. `extra_migrations_package` typically not relevant — schemaless. |
| MySQL | Mirror `OrchidPostgresChatStorage`'s shape but adjust DDL + DSN parsing. Honor migrations. |
| In-memory (tests) | Skip the file I/O and keep two dicts on the instance. Acceptable for unit tests; fails as production storage. |

For SQL-backed implementations, study
`orchid_ai.persistence.postgres.OrchidPostgresChatStorage` and
`orchid_ai.persistence.sqlite.OrchidSQLiteChatStorage` for the
canonical migration pattern via `OrchidMigrationRunner`.

## Contract checklist

When implementing your own `OrchidChatStorage`, verify each of the
following before declaring "done":

- [ ] Constructor accepts `dsn: str` and `extra_migrations_package: str | None`.
- [ ] `init_db()` is idempotent — running it twice is a no-op.
- [ ] `close()` releases pools/handles even when `init_db()` was never called.
- [ ] `create_chat()` returns a fresh UUID-keyed `OrchidChatSession`.
- [ ] `add_message()` touches the parent session's `updated_at`.
- [ ] `list_chats()` is sorted by `updated_at` descending.
- [ ] `get_messages()` is sorted by `created_at` ascending and respects `limit` + `offset`.
- [ ] `delete_chat()` cascades to that chat's messages.
- [ ] Concurrent `add_message()` calls within one process don't interleave (use a lock or DB transaction).
