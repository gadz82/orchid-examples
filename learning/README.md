# Learning Example — Cron-Driven Fan-Out

A personalized weekly learning digest system demonstrating **Pollen + Bloom** scheduled triggers: a single cron tick fans out into parallel Bloom runs, one per active learner, each generating a personalized digest under the `addressed_to_user` identity.

## What It Demonstrates

- **Scheduled cron triggers** — APScheduler-driven weekly digest at Monday 06:00 UTC
- **One-to-many fan-out** — Single signal produces N parallel Bloom runs (one per user)
- **`addressed_to_user` identity** — Service account acts on behalf of users without being the user
- **Per-user parallelism** — `parallelism: per_user` ensures isolated execution per learner
- **Visibility filtering (§26)** — Each user sees only their own digest, not others'
- **Custom signal producer** — `WeeklyDigestFanoutProducer` enumerates active learners and emits signals

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Scheduler | `APSchedulerBackend` with cron expression |
| Producer | Custom `WeeklyDigestFanoutProducer` |
| Identity | `addressed_to_user` with `orchid_ai.identity.OAuthMintingMixin` |
| Storage | `SQLiteEventStorage` + `SQLiteSignalQueue` |
| Agent | `GenericAgent` with personalized prompt |
| Parallelism | `parallelism: per_user` for isolated runs |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Cron Schedule  │────▶│  Fanout         │────▶│  N Signals       │
│  (Mon 06:00)    │     │  Producer       │     │  (one per user)  │
│  UTC            │     │                 │     │                  │
└─────────────────┘     └─────────────────┘     └──────────────────┘
                                                        │
                                                        ▼
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Bloom Run #1    │     │  Bloom Run #2   │     │  Bloom Run #N    │
│  (learner Alice) │     │  (learner Bob)  │     │  (learner Carol) │
│  addressed_to:   │     │  addressed_to:  │     │  addressed_to:   │
│  alice@tenant    │     │  bob@tenant     │     │  carol@tenant    │
└──────────────────┘     └─────────────────┘     └──────────────────┘
```

## Prerequisites

- Ollama running with `ollama pull llama3.2`
- Python 3.11+ with `orchid-ai` and `orchid-cli` installed

## Usage

### Via CLI

```bash
# Install dependencies (from repo root)
pip install -e orchid -e orchid-cli

# Start interactive session
orchid chat interactive --config examples/learning/orchid.yml

# Check scheduled triggers
orchid schedules list --config examples/learning/orchid.yml

# Emit a manual signal (bypass cron)
orchid signals emit weekly-digest.due \
  --payload '{"learner_id": "alice", "week": 23}' \
  --tenant-key demo-tenant \
  --user alice@example.com \
  --config examples/learning/orchid.yml
```

### Via API

```bash
ORCHID_CONFIG=examples/learning/orchid.yml \
  uvicorn orchid_api.main:app --port 8000

# List schedules
curl http://localhost:8000/schedules

# Emit signal manually
curl -X POST http://localhost:8000/signals \
  -H "Content-Type: application/json" \
  -d '{
    "type": "weekly-digest.due",
    "tenant_key": "demo-tenant",
    "user_id": "alice@example.com",
    "payload": {"learner_id": "alice", "week": 23}
  }'
```

## File Layout

```
examples/learning/
├── orchid.yml              # Runtime config (SQLite, scheduler)
├── agents.yaml             # Agent + events configuration
├── identity.py             # LearningIdentityResolver with mint_for_user()
├── producers/
│   ├── __init__.py
│   └── weekly_digest.py    # Custom signal producer (fan-out logic)
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_weekly_digest_fanout.py  # Fan-out behavior test
```

## Configuration Walkthrough

### Trigger Definition

```yaml
events:
  triggers:
    - id: weekly-digest
      signal_pattern:
        type: weekly-digest.due
      identity:
        mode: addressed_to_user
        addressed_to: "${signal.user_id}"
      agent_pipeline: [digest]
      parallelism: per_user
      respect_chat_binding: false
```

- **`signal_pattern`** — Matches signals of type `weekly-digest.due`
- **`identity.mode: addressed_to_user`** — Run visible to the addressed user
- **`addressed_to`** — Template resolving to signal's `user_id` field
- **`parallelism: per_user`** — One run per unique user, executed in parallel
- **`respect_chat_binding: false`** — Not chat-bound; runs independently

### Custom Producer

The `WeeklyDigestFanoutProducer` (in `producers/weekly_digest.py`):

```python
class WeeklyDigestFanoutProducer(OrchidSignalProducer):
    async def produce(self, auth: OrchidAuthContext) -> None:
        # Enumerate active learners from database
        learners = await self.get_active_learners()
        
        # Emit one signal per learner
        for learner in learners:
            await self.emit_signal(
                signal_type="weekly-digest.due",
                tenant_key=auth.tenant_key,
                user_id=learner.email,
                payload={"learner_id": learner.id, "week": current_week()},
            )
```

### Identity Resolver

The `LearningIdentityResolver` implements `mint_for_user()`:

```python
class LearningIdentityResolver(OrchidIdentityResolver, OAuthMintingMixin):
    async def mint_for_user(
        self,
        *,
        tenant_key: str,
        user_id: str,
        reason: str,
    ) -> OrchidAuthContext:
        # Mint a service-account token that acts as the user
        return OrchidAuthContext(
            tenant_key=tenant_key,
            user_id=user_id,
            bearer_header=None,  # Service account
            roles={"service_account"},
        )
```

## Visibility Model (§26)

Each Bloom run is created with `visibility: addressed` and `addressed_to_user_id` set to the learner's ID. This means:

- **Alice** sees only her digest run in `/runs` and `/bloom`
- **Bob** sees only his digest run
- **Admins** (with `admin` role) see all runs across all users

The 404-never-403 contract applies: non-owners requesting another user's run get 404, not 403.

## Sample Output

When the cron fires at Monday 06:00 UTC:

```
[SchedulerProducer] Cron fired: weekly-digest
[WeeklyDigestFanoutProducer] Found 3 active learners
[WeeklyDigestFanoutProducer] Emitting signal for alice@example.com
[WeeklyDigestFanoutProducer] Emitting signal for bob@example.com
[WeeklyDigestFanoutProducer] Emitting signal for carol@example.com
[BloomRunner#1] Starting run for alice@example.com
[BloomRunner#2] Starting run for bob@example.com
[BloomRunner#3] Starting run for carol@example.com
[BloomRunner#1] Finished: digest generated for alice
[BloomRunner#2] Finished: digest generated for bob
[BloomRunner#3] Finished: digest generated for carol
```

Each user receives their personalized digest in their chat (if `respect_chat_binding: true`) or as a standalone run (current configuration).

## Contrast with Other Examples

| Example | Trigger Type | Fan-Out | Identity Mode |
|---------|-------------|---------|---------------|
| **learning** | **Cron** | **Yes (N users)** | **addressed_to_user** |
| helpdesk | Webhook + Cron | No | addressed_to_user |
| basketball | Chat message | No | N/A |
| restaurant | Chat message | No | N/A |

## Extending the Example

### Add More Triggers

```yaml
events:
  triggers:
    - id: monthly-review
      signal_pattern:
        type: monthly-review.due
      schedule:
        cron: "0 6 1 * *"  # First of month at 06:00
      # ... rest of config
```

### Enable Chat Binding

Set `respect_chat_binding: true` and provide a `chat_binding` in the signal payload to append results directly to a user's chat.

### Add RAG

Enable RAG in `agents.yaml` to let the digest agent retrieve from the user's personal learning history:

```yaml
agents:
  digest:
    rag:
      enabled: true
      scope:
        include_user: true
      retrieval_strategy: simple
```

## Next Steps

After exploring learning:
- **helpdesk** — Webhook-driven event workflows
- **mcp-auth** — MCP authentication patterns
- **travel-agency** — HITL tool approval with checkpointer
