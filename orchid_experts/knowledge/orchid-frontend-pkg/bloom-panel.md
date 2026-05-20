<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# Bloom Panel

The Bloom operator panel displays Pollen+Bloom event activity in the chat interface, showing background job runs and their progress. It integrates with the SSE stream to provide real-time updates of event-driven agent executions.

## BloomPanel Component

```tsx
<BloomPanel
  chatId="chat-123"
/>
```

The component auto-connects to the Bloom SSE stream and displays:

## Features

### Job Run List

Active and recent Bloom runs are displayed with their status:

```
┌─────────────────────────────────────┐
│ Bloom Runs                          │
├─────────────────────────────────────┤
│ ✅ support-triage  ·  2 min ago     │
│ ⏳ daily-digest    ·  running now   │
│ ❌ report-gen      ·  5 min ago     │
└─────────────────────────────────────┘
```

Each entry shows:
- Trigger ID and friendly name.
- Status icon (pending, running, completed, failed).
- Relative timestamp.
- Click to expand for details.

### Progress Indicators

Running jobs show live progress:

```tsx
<JobProgress
  jobRunId="run-1"
  status="running"
  progress="Running agent: support"
  startedAt="2025-01-01T00:00:00Z"
/>
```

Progress updates arrive via SSE and update in real-time.

### In-Chat Notifications

When a Bloom run has `respect_chat_binding: true`, the result appears as a message in the chat:

```tsx
<MessageBubble
  role="assistant"
  content="Bloom run result: Ticket #456 triaged..."
  metadata={{ origin: "bloom", trigger_id: "support-triage" }}
/>
```

The message includes:
- A "Bloom" badge to distinguish from user-initiated responses.
- The trigger name for context.
- A link to view the full Bloom run details.

### Run Details Panel

Clicking a run expands its details:

```tsx
<RunDetails jobRunId="run-1">
  <SignalPayload>
    { type: "support.ticket.created", payload: { ... } }
  </SignalPayload>
  <PromptRendered>
    A new ticket arrived: Login issue.
    Draft an initial reply.
  </PromptRendered>
  <AgentOutput>
    Here's a draft reply for the ticket...
  </AgentOutput>
  <Timeline>
    Signal received → Trigger matched → Agent invoked → Completed
  </Timeline>
</RunDetails>
```

## SSE Integration

Bloom events stream alongside chat events via the same SSE connection:

```
event: job_run.started
data: {"job_run_id": "run-1", "trigger_id": "support-triage"}

event: job_run.progress
data: {"job_run_id": "run-1", "progress": "Running agent: support"}

event: job_run.completed
data: {"job_run_id": "run-1", "result": "...", "duration_ms": 2500}

event: job_run.failed
data: {"job_run_id": "run-1", "error": "Token refresh failed"}
```

The BloomPanel subscribes to these events via the `useChatStream` hook.

## Visibility Filter

Jobs are filtered by visibility level set in the trigger configuration:
- `actor` — Only the triggering user sees the run.
- `addressed` — The addressed user sees it.
- `tenant` — All users in the tenant see it.
- `admin` — Only admin users see it.

The filter is enforced by the API before SSE events are dispatched. The frontend does not need to implement its own visibility logic — it simply renders whatever events the API sends.

## Error Handling

Failed Bloom runs display error details:

```tsx
<JobError
  error="Token refresh failed: connection refused"
  retryable={true}
  attemptNumber={3}
  maxAttempts={5}
/>
```

Users with appropriate permissions can manually retry failed runs.

## Refresh and Polling

The BloomPanel:
- Connects to SSE for real-time updates.
- Falls back to polling if SSE disconnects.
- Shows a "Reconnecting..." indicator during reconnection.
- Loads recent runs on mount (up to 50).
