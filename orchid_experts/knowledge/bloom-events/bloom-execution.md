<!-- Source: derived from orchid-website/src/content/concepts/pollen-bloom.mdx, orchid/README.md, and codebase analysis -->

# Bloom Execution

Bloom is the execution layer that matches signals to triggers and runs agent invocations. It turns incoming signals into LangGraph runs under a synthesized `OrchidAuthContext`.

## How Bloom Works

```
Signal → Queue → Processor
                  │
                  │ 1. Dequeue signal
                  │ 2. Match signal to triggers
                  │ 3. Evaluate JMESPath `when` conditions
                  │ 4. Synthesise OrchidAuthContext
                  │ 5. Run LangGraph supervisor
                  │ 6. Record JobRun result
                  ▼
                JobRun
```

## Trigger Matching

### First-Pass Match

Triggers match signals by type:

```yaml
triggers:
  - id: support-ticket-triage
    on:
      signal: support.ticket.created
```

A signal with type `support.ticket.created` matches this trigger.

### JMESPath When Conditions

Optional JMESPath boolean expressions for fine-grained matching:

```yaml
triggers:
  - id: high-priority-triage
    on:
      signal: support.ticket.created
      when: "payload.priority == 'high'"
```

The expression is compiled at registration time — invalid JMESPath fails boot, not run-time.

## JobSpec and JobRunner

### JobSpec

Defines what the Bloom run should do:

```yaml
emits:
  agent: support
  prompt_template: |
    A new ticket arrived: {{payload.subject}}.
    Draft an initial reply.
  identity:
    mode: addressed_to_user
    service_account: support-bot
    user_id_from: payload.requester.id
```

- **`agent`** — Agent name to invoke (must exist in `agents:`).
- **`prompt_template`** — Mustache-style `{{var}}` template rendered against the signal envelope.
- **`identity`** — Discriminated union for the `OrchidAuthContext` (see identity-modes.md).

### JobRunner

Invokes the LangGraph supervisor under the synthesized auth context:

```python
class JobRunner:
    async def run(self, job_spec: JobSpec, signal: Signal) -> JobRun:
        auth_context = await self._synthesise_auth(job_spec.identity, signal)
        result = await self._graph.ainvoke({
            "messages": [{"role": "user", "content": prompt}],
            "auth_context": auth_context,
        })
        return JobRun(
            id=str(uuid.uuid4()),
            trigger_id=job_spec.trigger_id,
            signal_id=signal.id,
            status="completed",
            result=result,
        )
```

## JobRun

Records the result of a Bloom execution:

```python
@dataclass
class JobRun:
    id: str
    trigger_id: str
    signal_id: str
    status: str              # pending | running | completed | failed
    attempt_number: int
    started_at: datetime
    completed_at: datetime | None
    result: dict | None
    error: str | None
```

### Replay Safety

The `(trigger_id, signal_id, attempt_number)` UNIQUE constraint ensures that retries create new `JobRun` rows (never in-place updates) and the same signal isn't processed twice.

## Chat Binding

When `respect_chat_binding: true` and the signal carries a `ChatBinding`, the run's final `AIMessage` lands in the target chat:

```python
# The AIMessage is appended to the chat with metadata.origin = "bloom"
await chat_storage.add_message(
    chat_id=chat_binding.chat_id,
    role="assistant",
    content=result,
    metadata={"origin": "bloom", "trigger_id": trigger_id},
)
```

This allows Bloom runs to surface results directly in user-facing chats.
