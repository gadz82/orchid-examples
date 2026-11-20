# Event-Driven Data Pipeline Example

The customer-health pipeline from the direct example, started by Pollen signals
instead of a caller:

- a **bearer-authenticated webhook** starts a per-user Bloom run and, when the
  signal carries a chat binding, posts the pipeline summary back to that chat;
- a **cron schedule** starts a service-account run every morning.

The pipeline itself is the same typed DAG: deterministic loading, a map fan-out,
LLM assessment and report, a decision route, an agent escalation, a
sub-pipeline snapshot and an emit job. No frontend, no MCP gateway and no
Qdrant. Chat and event state live in SQLite in the container; the test suite
uses SQLite event storage and an in-memory chat backend.

## Run with Docker

From `workspace-py`:

```bash
make demo-data_pipeline_events    # via script/start_data_pipeline_events.sh
make run-data_pipeline_events     # docker compose up --build
```

Or run the example's own compose file:

```bash
cp .env.example .env
docker compose up --build
```

The API listens on `http://localhost:8080`.

## Send a request signal

The webhook source accepts `pipeline.customer_health.requested` with the
`PIPELINE_INGEST_TOKEN` bearer:

```bash
curl -sS -X POST http://localhost:8080/signals \
  -H 'X-Orchid-Source: customer-health-webhook' \
  -H 'Authorization: Bearer dev-ingest-token' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "pipeline.customer_health.requested",
    "tenant_key": "data-pipeline-demo",
    "user_id": "dev-user",
    "payload": {"customer_id": "C-100"}
  }'
```

The trigger copies `payload` into the pipeline input (`input_from: payload`),
runs as the signal's user (`act_as_user`) and records `actor` visibility. The
local resolver maps every HTTP bearer to `data-pipeline-demo/dev-user`; keep the
signal `user_id` aligned with that (or replace `identity.py` with your IdP).

To post the summary to a chat, create a chat and add a binding:

```bash
curl -sS -X POST http://localhost:8080/chats \
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' -d '{}'
```

```json
"chat_binding": {"chat_id": "<chat-id>", "mode": "append_final_message"}
```

The binding is honored only when the signal user owns the chat (or an admin
writes it); a foreign chat fails the Bloom run before the pipeline starts.

The assistant message carries `metadata.origin = "bloom"`, the trigger id, the
pipeline name and the pipeline run id. Without a binding the run is still
recorded and visible through `/runs`; nothing is posted to a chat.

## Schedule

`agents.yaml` declares a daily cron schedule and a matching `cron` trigger:

```yaml
schedules:
  - id: customer-health-daily
    cron: "0 6 * * *"
    trigger_id: customer-health-scheduled
    identity: { mode: service_account, name: scheduler }
```

The scheduler producer emits a synthetic `cron` signal, the trigger runs the
pipeline with `customer_id: C-SCHEDULED`, and the run gets `tenant` visibility
under the `scheduler` service account. Change the cron expression in both the
schedule and the trigger to test a different cadence.

## Inspect runs

```bash
curl -sS http://localhost:8080/runs -H 'Authorization: Bearer dev-token'
curl -sS http://localhost:8080/runs/<run-id> -H 'Authorization: Bearer dev-token'
```

`/schedules` is admin-only in v1; the demo resolver has no roles, so use the
event store or a resolver with an `admin` role to inspect schedules.

Run visibility follows the identity mode: `act_as_user` request runs are
visible to that user (and admins) in `data-pipeline-demo`; the scheduled
service-account run lives in the `default` tenant, so the demo webhook identity
does not see it. Cross-tenant reads return 404.

## Tests

```bash
cd workspace-py
../.venv/bin/python -m pytest examples/data_pipeline_events \
  -m "not integration" --import-mode=importlib -x
```

The suite is hermetic: SQLite event storage in a temp file, an in-memory chat
store, a deterministic chat model and no network or Ollama. It covers trigger
parsing, HTTP signal ingest, the pipeline `JobRun`, result shape, chat binding,
the schedule producer, visibility and the emit sink.

## Files

| File | Purpose |
|------|---------|
| `agents.yaml` | Shapes/relations, the customer-health DAG, Pollen triggers, schedule and ingestion source |
| `orchid.yml` | API config: identity resolver, SQLite chat storage, null vector backend, local-sink startup hook |
| `identity.py` | Permissive local resolver for `act_as_user`, service accounts and minting |
| `steps.py` | Deterministic operators copied from the direct example |
| `hooks/startup.py` | Local signal sink for direct runs without the events dispatcher |
| `tests/` | Trigger, signal, chat-binding and schedule e2e coverage |
