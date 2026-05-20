<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx, orchid/README.md, and codebase analysis -->

# Retry and Queues

The Pollen+Bloom system uses a two-level retry architecture: queue-level retry for signal dequeuing and trigger-level retry for Bloom execution failures.

## Signal Queue

### Queue Backends

| Backend | Description |
|---------|-------------|
| `InMemorySignalQueue` | Non-durable queue for tests/demos. |
| `SQLiteSignalQueue` | Durable queue for single-process deployments. |
| `PostgresSignalQueue` | Durable queue with `FOR UPDATE SKIP LOCKED` for multi-process. |
| `RelayingSignalQueue` | Publish-then-mark adapter for external buses. |

### Queue Configuration

```yaml
events:
  queue:
    class: orchid_ai.events.queues.postgres.PostgresSignalQueue
    notify_enabled: true
    poll_interval_ms: 200
    lease_seconds: 30
    max_attempts: 5
```

### Queue Retry

When a processor fails to process a signal:

1. The signal's lease expires after `lease_seconds`.
2. Another processor picks up the signal.
3. After `max_attempts` failed attempts, the signal moves to the dead-letter table.

### Deduplication

Signals with the same `dedupe_key` are deduplicated at the queue level, preventing duplicate processing.

## Trigger-Level Retry

Separate from queue retry. Controls what happens when a Bloom run fails:

```yaml
triggers:
  - id: support-triage
    retry:
      max: 5
      backoff: exponential
      jitter: true
      initial_delay_seconds: 1.0
      max_delay_seconds: 300.0
```

### Retry Behavior

Retries create **new `JobRun` rows** with `attempt_number + 1` — never in-place updates. The `(trigger_id, signal_id, attempt_number)` UNIQUE constraint provides replay safety.

### Backoff Strategies

| Strategy | Delay Calculation |
|----------|------------------|
| `fixed` | `initial_delay` (constant) |
| `linear` | `initial_delay * attempt_number` |
| `exponential` | `initial_delay * 2^attempt_number` |

## Dead Letter Queue

Signals that exhaust all queue retry attempts move to the dead-letter table for inspection and manual intervention.

## Processor Configuration

```yaml
events:
  processors:
    - class: orchid_ai.events.processors.asyncio_pool.AsyncioWorkerPoolProcessor
      concurrency: 4
      poll_interval_ms: 200
      lease_seconds: 30
      max_attempts: 5
      drain_timeout_seconds: 10.0
```

### Parallelism

Triggers control concurrent execution:
- **`per_user`** (default) — Serialized by user to avoid races on MCP capability cache.
- **`per_tenant`** — Serialized by tenant.
- **`unbounded`** — No serialization for independent workloads.
