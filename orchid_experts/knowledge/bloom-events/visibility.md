<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx and codebase analysis -->

# Visibility

Bloom run visibility controls who can see run results, both in the streaming UI and the `/auth/resolve-identity` endpoint. Each trigger can specify its visibility level.

## Visibility Levels

| Level | Description | Default For |
|-------|-------------|-------------|
| `actor` | Only the user who triggered the run can see it. | `act_as_user` |
| `addressed` | The addressed user (from `addressed_to_user`) can see it. | `addressed_to_user` |
| `tenant` | All users in the tenant can see it. | (none) |
| `admin` | Only admin users can see it. | `service_account` |

## Default Inference

When `visibility` is not explicitly set, it's inferred from the identity mode:

```yaml
triggers:
  - id: user-workflow
    emits:
      identity:
        mode: act_as_user
      # visibility defaults to actor
```

### Compatibility Enforcement

The `(identity, visibility)` compatibility matrix is enforced at config-load AND registration-time:

| Identity Mode | Allowed Visibility |
|--------------|-------------------|
| `service_account` | `admin`, `tenant` |
| `addressed_to_user` | `addressed`, `tenant`, `admin` |
| `act_as_user` | `actor`, `tenant`, `admin` |

Incompatible combinations fail at boot time.

## Streaming Visibility

Bloom runs stream their progress via SSE, but the visibility filter controls who receives the events:

```
SSE event: job_run.started
data: {"job_run_id": "...", "trigger_id": "...", "visibility": "actor"}

SSE event: job_run.completed
data: {"job_run_id": "...", "visibility": "actor"}
```

The streaming proxy filters events based on the viewer's identity and the visibility level.

## Job Run Status

Job runs can be queried via the API:

```
GET /api/events/jobs?status=completed&trigger_id=support-triage
```

Returns job runs filtered by:
- **Status** — `pending`, `running`, `completed`, `failed`.
- **Trigger ID** — Specific trigger.
- **Time range** — `since`, `until`.
- **Visibility** — Only runs visible to the querying user.

## In-Chat Progress

When `respect_chat_binding: true`, Bloom run progress can appear in the user's chat:

- The streaming UI shows "Bloom run in progress..." indicators.
- The final result lands as a message with `metadata.origin: "bloom"`.
- The user can see the run's progress in the Bloom operator panel.
