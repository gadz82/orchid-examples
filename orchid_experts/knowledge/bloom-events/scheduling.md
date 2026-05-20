<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx, orchid/README.md, and codebase analysis -->

# Scheduling

Orchid's Pollen+Bloom system supports cron-based and interval-based scheduling for recurring agent invocations.

## Schedules and Triggers

Scheduling involves two YAML sections:

### schedules Section

Defines when signals are fired:

```yaml
schedules:
  - id: morning-digest
    cron: "0 7 * * 1-5"
    trigger_id: morning-digest
    identity:
      mode: service_account
      name: digest-bot

  - id: health-check
    interval_seconds: 300
    trigger_id: health-check
    identity:
      mode: service_account
      name: monitor-bot
```

### triggers Section

Defines what happens when a scheduled signal fires:

```yaml
triggers:
  - id: morning-digest
    on:
      signal: cron
      cron: "0 7 * * 1-5"
    emits:
      agent: notifications
      prompt_template: "Build the morning digest for {{tenant_key}}"
      identity:
        mode: service_account
        name: digest-bot
```

## Cron Syntax

Standard 5-field cron syntax:

```
* * * * *
│ │ │ │ │
│ │ │ │ └── day of week (0-6, 0=Sun)
│ │ │ └──── month (1-12)
│ │ └────── day of month (1-31)
│ └──────── hour (0-23)
└────────── minute (0-59)
```

Examples:

| Cron | Meaning |
|------|---------|
| `0 7 * * 1-5` | 7 AM, Monday-Friday |
| `0 */6 * * *` | Every 6 hours |
| `30 9 1 * *` | 9:30 AM, 1st of every month |
| `0 0 * * 0` | Midnight every Sunday |

## Interval Schedules

Simpler alternative to cron:

```yaml
schedules:
  - id: health-check
    interval_seconds: 300  # Every 5 minutes
    trigger_id: health-check
```

Interval schedules start immediately and repeat at the specified interval.

## SchedulerProducer

The `SchedulerProducer` drives the configured scheduler:

```yaml
events:
  scheduler:
    class: orchid_ai.events.schedulers.apscheduler.APSchedulerBackend
  producers:
    - class: orchid_ai.events.producers.scheduler.SchedulerProducer
```

The `APSchedulerBackend` wraps `apscheduler.AsyncIOScheduler` (no SQLAlchemy). Durability lives in the `schedules` table — APScheduler's in-memory jobstore is re-populated on every boot.

### Signal Emission

When a schedule fires, the `SchedulerProducer`:

1. Creates a synthetic `cron` signal with `dedupe_key = "<schedule_id>:<fire_iso>"`.
2. Passes the signal through `dispatcher.ingest()`.
3. The dedupe key prevents duplicate processing if the scheduler fires multiple times.

## Cross-Field Validation

When `events.enabled: true`:

- Every `schedule.trigger_id` must reference a trigger declared in the same file (forward references not supported).
- Every schedule's matching trigger must declare `on.signal: cron`.
- Invalid configurations fail at boot time.

## Enabled Flag

Individual schedules can be disabled without removing them:

```yaml
schedules:
  - id: daily-report
    cron: "0 8 * * *"
    trigger_id: daily-report
    enabled: false  # Paused
```

Disabled schedules are persisted but not loaded into the scheduler.
