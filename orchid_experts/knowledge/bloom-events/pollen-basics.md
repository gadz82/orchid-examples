<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx, orchid/README.md, and codebase analysis -->

# Pollen Basics

Pollen is the signal ingestion layer of Orchid's event-driven automation system. It receives signals from external sources (webhooks, cron, internal emissions) and persists them for Bloom execution.

## Signal

A `Signal` is the core unit of event data in Pollen:

```python
@dataclass
class Signal:
    id: str
    type: str                    # e.g., "support.ticket.created"
    tenant_key: str
    payload: dict[str, Any]      # Arbitrary JSON payload
    dedupe_key: str | None       # For idempotent ingestion
    metadata: dict[str, Any]     # Source info, timestamps
```

### Signal Types

Signal types use a dotted naming convention:

```
support.ticket.created
support.ticket.updated
cron.daily-digest
user.registered
system.alert.critical
```

The type is used for trigger matching (first-pass match on `events.triggers[].on.signal`).

## Signal Sources

Signals enter Pollen through various sources:

### HTTP Webhooks

External systems send HTTP POST requests to the API:

```
POST /api/events/ingest
Content-Type: application/json
X-Signature: sha256=...

{
  "type": "support.ticket.created",
  "payload": { ... }
}
```

Webhook sources are configured in the `events.ingestion.sources` section.

### Scheduler (Cron/Interval)

The `SchedulerProducer` fires synthetic `cron` signals at configured intervals:

```yaml
schedules:
  - id: morning-digest
    cron: "0 7 * * 1-5"
    trigger_id: morning-digest
    identity:
      mode: service_account
      name: digest-bot
```

### Internal Emissions

Agents can emit signals programmatically:

```python
await self.emit_signal(
    type="agent.task.completed",
    payload={"task_id": "123", "result": "done"},
)
```

The `InternalEmissionProducer` wires these emissions through `DispatcherSignalEmitter`.

## SignalIngestionSource

Each webhook source is configured with:

- **`id`** — Unique source identifier.
- **`validator`** — Authentication validator (HMAC or Bearer).
- **`allowed_types`** — Allowlist of signal types this source can emit.
- **`secret_ref`** — Reference to the validation secret (e.g., `env:HMAC_SECRET`).

## Validators

### HMACValidator

Validates webhook signatures using SHA-256 HMAC:

```yaml
validator:
  class: orchid_ai.events.auth.HMACValidator
  secret_ref: env:SUPPORT_HMAC_SECRET
```

Constant-time comparison against the raw body.

### BearerValidator

Validates via bearer token:

```yaml
validator:
  class: orchid_ai.events.auth.BearerValidator
  secret_ref: env:WEBHOOK_BEARER_TOKEN
```

## Deduplication

Signals carry an optional `dedupe_key` for idempotent ingestion:

```python
signal = Signal(
    type="support.ticket.created",
    dedupe_key="ticket-123:v2",
    ...
)
```

The queue backends use `(dedupe_key, type)` for deduplication, preventing the same event from being processed multiple times.

## Middleware

Optional `SignalIngestMiddleware` chain runs on every `dispatcher.ingest()` call before persistence:

```yaml
middleware:
  - class: orchid_ai.events.middleware.EnrichmentMiddleware
  - class: orchid_ai.events.middleware.TaggingMiddleware
```

Middleware can enrich signals with additional context, add tags, or filter signals before they reach the queue.
