# Helpdesk Example — Event-Driven Workflow

A three-agent helpdesk system demonstrating **Pollen + Bloom** event-driven activation: customer tickets flow through `triage` → `support` → `escalation` agents via background Bloom runs, with results appended back into the customer's chat.

## What It Demonstrates

- **Pollen + Bloom fan-out** — Incoming signals trigger multi-step Bloom runs that execute agent pipelines in the background
- **Event-driven agent activation** — Agents run as Bloom triggers, not just in response to chat messages
- **SQLite event storage** — Persistent signal/queue/store using built-in SQLite (PostgreSQL plugin available via `orchid-storage-postgres`)
- **Three-agent routing pipeline** — Tickets automatically flow through triage, support, and escalation based on priority
- **Custom event producers** — HTTP webhook ingestion for external ticketing systems
- **Identity minting** — Service-account Bloom runs that act on behalf of users via `OrchidIdentityResolver.mint_for_user()`

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Event storage | `SQLiteEventStorage` (built-in) — Postgres events plugin roadmap item |
| Signal queue | `SQLiteSignalQueue` with polling — Postgres signal queue plugin roadmap item |
| Scheduler | `APSchedulerBackend` for cron triggers |
| Producers | `HTTPIngestionProducer` (webhook), `SchedulerProducer` (cron) |
| Processors | `AsyncioWorkerPoolProcessor` with concurrency control |
| Auth | Dev bypass mode (configurable to full OAuth) |
| LLM | Gemini (`gemini-flash-latest`, `gemini-embedding-001`) |

## Architecture

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  HTTP Webhook    │────▶│  Pollen Signals │────▶│  Bloom Triggers  │
│  (ticketing sys) │     │  (persisted)    │     │  (declared in YAML)│
└──────────────────┘     └─────────────────┘     └──────────────────┘
                                                        │
                                                        ▼
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Chat Message    │────▶│  Bloom Run      │────▶│  Agent Pipeline  │
│  (user)          │     │  (background)   │     │  triage→support→ │
└──────────────────┘     └──────────────────┘     │  escalation      │
                                                  └──────────────────┘
```

## Prerequisites

- Python 3.11+ with `orchid-ai` and `orchid-api` installed
- Gemini API key (for LLM and embeddings)

## Usage

### Via Docker Compose

```bash
# From repo root
docker compose -f docker-compose.demo.yml up --build
```

This starts the API, Qdrant, and all dependencies.

### Environment Variables

Create `.env.local` from `.env.example`:

```bash
cd examples/helpdesk
cp .env.example .env.local
# Edit .env.local and set:
#   GEMINI_API_KEY=your_actual_key
```

### Via Standalone API

```bash
export GEMINI_API_KEY=your_key
export HELPDESK_DATABASE_URL=sqlite:///data/helpdesk.db

ORCHID_CONFIG=examples/helpdesk/config/orchid.yml \
  uvicorn orchid_api.main:app --port 8000
```

### Sending a Ticket

```bash
# Via webhook (external ticketing system)
curl -X POST http://localhost:8000/signals \
  -H "Content-Type: application/json" \
  -d '{
    "type": "support.ticket.created",
    "tenant_key": "helpdesk-demo",
    "payload": {
      "subject": "Cannot access my account",
      "priority": "high",
      "customer_id": "cust-123"
    }
  }'

# Via CLI (interactive)
orchid chat interactive --config examples/helpdesk/config/orchid.yml
```

## File Layout

```
examples/helpdesk/
├── config/
│   ├── orchid.yml          # Runtime config (LLM, RAG, storage)
│   └── agents.yaml         # Agents + events configuration
├── agents/
│   ├── __init__.py
│   └── support.py          # Custom SupportAgent class
├── tools/
│   └── tickets.py          # create_ticket, update_status, get_ticket
├── storage/
│   └── __init__.py         # (uses built-in Postgres storage)
├── identity.py             # HelpdeskIdentityResolver
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_high_priority_e2e.py  # End-to-end priority test
```

## Agents

| Agent | Role | Tools |
|-------|------|-------|
| `triage` | Classifies ticket priority and routes | None (routing only) |
| `support` | Handles standard support requests | `create_ticket`, `update_status` |
| `escalation` | Handles high-priority/sensitive issues | Custom `SupportAgent` logic |

## Event Configuration

The `events:` block in `agents.yaml` defines:

1. **Store** — Postgres-backed event persistence
2. **Queue** — Polling-based signal queue with lease management
3. **Scheduler** — APScheduler for cron-based triggers
4. **Producers** — HTTP webhook ingestion + scheduler-driven cron jobs
5. **Processors** — Async worker pool with configurable concurrency
6. **Triggers** — Pattern-matching rules that fire Bloom runs

```yaml
events:
  enabled: true
  triggers:
    - id: high-priority-escalation
      signal_pattern:
        type: support.ticket.created
        payload.priority: high
      identity:
        mode: addressed_to_user
      agent_pipeline: [triage, escalation]
```

## Visibility Model (§26)

Bloom runs support visibility filtering:
- **`addressed_to_user`** — Run appears only to the specified user
- **`service_account`** — Run visible to admins/operators
- **`act_as_user`** — Run executes with user's RAG scope access

The helpdesk example uses `addressed_to_user` so customers only see their own ticket processing.

## Pollen + Bloom Endpoints

When `events.enabled: true`, these endpoints are active:

| Endpoint | Purpose |
|----------|---------|
| `POST /signals` | Ingest a signal (webhook) |
| `GET /signals` | List signals (admin only) |
| `GET /jobs` | List trigger definitions |
| `GET /jobs/{trigger_id}/runs` | List runs for a trigger |
| `GET /runs` | List runs visible to caller |
| `GET /runs/{run_id}/stream` | SSE stream of run events |
| `POST /runs/{run_id}/cancel` | Cancel a running Bloom |
| `GET /schedules` | List cron schedules (admin only) |

## Contrast with Other Examples

| Example | Event-Driven | Storage | Complexity |
|---------|-------------|---------|------------|
| basketball | No | SQLite | Minimal |
| **helpdesk** | **Yes** | **Postgres** | **Medium** |
| learning | Yes (cron) | SQLite | Medium |
| restaurant | No | SQLite | Medium |

## Next Steps

After exploring helpdesk:
- **learning** — Cron-driven fan-out to multiple users
- **mcp-auth** — MCP authentication patterns
- **wiki** — Advanced RAG strategies with hybrid retrieval
