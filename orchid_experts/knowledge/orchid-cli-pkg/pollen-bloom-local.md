<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# Pollen+Bloom Local

The CLI supports running Pollen+Bloom events in a local, in-process mode for testing, development, and short-lived invocations. This enables full event-driven automation without deploying the API server.

## Event Commands

### list-jobs

List Bloom job runs with filtering:

```bash
orchid pollen-bloom list-jobs \
  --status completed \
  --trigger support-triage \
  --limit 20
```

Output:

```
Job Runs (20 of 145)
┌──────────────────────┬──────────────────┬───────────┬─────────────────────┐
│ Job Run ID           │ Trigger          │ Status    │ Completed           │
├──────────────────────┼──────────────────┼───────────┼─────────────────────┤
│ run-abc123...        │ support-triage   │ completed │ 2025-06-01 10:30 UTC│
│ run-def456...        │ support-triage   │ completed │ 2025-06-01 10:28 UTC│
└──────────────────────┴──────────────────┴───────────┴─────────────────────┘
```

### list-signals

List Pollen signals:

```bash
orchid pollen-bloom list-signals \
  --type support.ticket.created \
  --limit 50
```

### trigger

Manually trigger a Bloom run for testing:

```bash
orchid pollen-bloom trigger \
  --trigger-id support-triage \
  --payload '{"priority": "high", "subject": "Login issue", "requester": {"id": "user-123"}}'
```

This creates a synthetic signal, runs it through trigger matching, and executes the Bloom. The result is displayed in the terminal.

## Local Mode (Long-Running)

Start the full Pollen+Bloom pipeline in-process:

```bash
orchid pollen-bloom start --config orchid.yml
```

This starts:
1. **Signal queue processor** — Drains the queue and executes Blooms (configurable concurrency).
2. **Scheduler** — Runs cron and interval schedules.
3. **Signal producers** — Internal emission producer for agent-emitted signals.
4. **Monitoring output** — Periodic status updates in the terminal.

The process runs until interrupted with `Ctrl+C`, which triggers a graceful shutdown.

### Configuration

Local mode respects the `events` section of `agents.yaml`:

```yaml
events:
  enabled: true
  store:
    class: orchid_ai.events.backends.sqlite.SQLiteEventStorage
  queue:
    class: orchid_ai.events.queues.sqlite.SQLiteSignalQueue
    poll_interval_ms: 200
    max_attempts: 5
  scheduler:
    class: orchid_ai.events.schedulers.apscheduler.APSchedulerBackend
  processors:
    - class: orchid_ai.events.processors.asyncio_pool.AsyncioWorkerPoolProcessor
      concurrency: 4
```

## Short-Lived Invocations

For one-off Bloom runs without starting the full pipeline:

```bash
orchid pollen-bloom run-once \
  --trigger-id support-triage \
  --signal-type support.ticket.created \
  --payload '{"priority": "high", "subject": "Test ticket"}'
```

This:
1. Creates a synthetic signal.
2. Matches it to the specified trigger.
3. Synthesizes the auth context from the trigger's identity mode.
4. Runs the LangGraph supervisor.
5. Displays the result.
6. Exits.

Perfect for CI/CD pipelines, testing trigger configurations, and debugging Bloom behavior.

## In-Memory vs Persistent Storage

### In-Memory (Default for One-Off Commands)

```yaml
events:
  queue:
    class: orchid_ai.events.queues.inmemory.InMemorySignalQueue
```

Signals and jobs are lost when the process exits. Suitable for `run-once` and testing.

### Persistent (For Local Mode)

```yaml
events:
  store:
    class: orchid_ai.events.backends.sqlite.SQLiteEventStorage
  queue:
    class: orchid_ai.events.queues.sqlite.SQLiteSignalQueue
```

Signals and job runs survive process restarts. Suitable for `pollen-bloom start` and local development.

## Testing Triggers

Local mode is ideal for testing triggers before deploying to production:

1. **Define a trigger** in `agents.yaml` with signal type, agent, and prompt template.
2. **Start local mode**: `orchid pollen-bloom start`.
3. **Emit a test signal**: `orchid pollen-bloom trigger --trigger-id my-trigger --payload '{...}'`.
4. **Check results**: `orchid pollen-bloom list-jobs --trigger my-trigger --status completed`.
5. **Debug**: check logs for errors, adjust trigger config, retry.

This fast iteration cycle avoids deploying to production for trigger testing.

## Watching Signals

In local mode, incoming signals and job runs are printed to the terminal:

```
[2025-06-01 10:30:00] Signal received: support.ticket.created (source: webhook)
[2025-06-01 10:30:01] Trigger matched: support-triage (signal: support.ticket.created)
[2025-06-01 10:30:01] Job started: run-abc123 (trigger: support-triage, agent: support)
[2025-06-01 10:30:03] Job completed: run-abc123 (duration: 2500ms)
```

Use the `--verbose` flag for more detailed output including LLM prompts and tool calls.
