<!-- Source: derived from orchid/README.md, orchid-website/src/content/configuration-reference/agents.mdx, and codebase analysis -->

# Guardrails

Orchid implements a 3-tier safety layer for AI guardrails: global input guardrails, per-agent guardrails, and global output guardrails. Guardrails run automatically at the appropriate points in the agent pipeline to enforce safety, compliance, and domain boundaries.

## 3-Tier Architecture

### Tier 1: Global Input Guardrails

Run on every user message **before** the supervisor processes it. Defined at the root level of `agents.yaml`:

```yaml
guardrails:
  input:
    - type: prompt_injection
      fail_action: block
    - type: content_safety
      fail_action: block
    - type: max_length
      fail_action: block
      config:
        max_characters: 5000
```

### Tier 2: Per-Agent Guardrails

Run when a specific agent is active, in addition to global guardrails. Defined within each agent:

```yaml
agents:
  my-agent:
    guardrails:
      input:
        - type: topic_restriction
          fail_action: warn
          config:
            allowed_topics: [topic1, topic2]
```

### Tier 3: Global Output Guardrails

Run on every response **before** returning it to the user. Defined at the root level:

```yaml
guardrails:
  output:
    - type: pii_detection
      fail_action: redact
      config:
        entities: [email, phone, credit_card]
```

## Guardrail Types

### prompt_injection

Detects attempts to override the system prompt or inject malicious instructions.

- **Detection:** Analyzes the user message for patterns that attempt to change the agent's behavior, ignore previous instructions, or reveal system prompts.
- **Fail actions:** `block` (reject the message), `warn` (allow but flag), `pass` (no action).

```yaml
- type: prompt_injection
  fail_action: block
```

### content_safety

Detects harmful, offensive, or inappropriate content.

- **Detection:** Analyzes content for violence, hate speech, sexual content, self-harm, and other safety categories.
- **Fail actions:** `block`, `warn`, `pass`.

```yaml
- type: content_safety
  fail_action: block
```

### max_length

Enforces a maximum message length to prevent token budget exhaustion.

- **Detection:** Checks if the message exceeds the configured character limit.
- **Fail actions:** `block`, `warn`, `pass`.
- **Config:** `max_characters` (integer).

```yaml
- type: max_length
  fail_action: block
  config:
    max_characters: 5000
```

### pii_detection

Detects personally identifiable information in content.

- **Detection:** Scans for email addresses, phone numbers, credit card numbers, SSNs, and other PII patterns.
- **Fail actions:** `redact` (replace with `[REDACTED]`), `warn`, `block`.
- **Config:** `entities` (list of entity types to detect).

```yaml
- type: pii_detection
  fail_action: redact
  config:
    entities: [email, phone, credit_card]
```

### topic_restriction

Ensures the query is within the agent's allowed domain.

- **Detection:** Analyzes the query against a list of allowed topic keywords. If the query doesn't match any allowed topics, it triggers the fail action.
- **Fail actions:** `warn` (allow but flag — useful for non-blocking domain enforcement), `block`.
- **Config:** `allowed_topics` (list of keyword terms).

```yaml
- type: topic_restriction
  fail_action: warn
  config:
    allowed_topics: [room, venue, floor, zone, direction, entrance, elevator]
```

### groundedness

Checks if the agent's response is grounded in the provided RAG context.

- **Detection:** Analyzes the response to determine if claims are supported by the retrieved documents.
- **Fail actions:** `warn`, `block`, `pass`.
- **Use case:** Prevents hallucination in RAG-powered agents.

```yaml
- type: groundedness
  fail_action: warn
```

## Fail Actions

| Action | Behavior |
|--------|----------|
| `block` | Reject the message/response. Return an error to the user. |
| `warn` | Allow the message/response but flag it (for logging or UI display). |
| `redact` | Replace detected content with `[REDACTED]` (PII only). |
| `pass` | No action (effectively disabled). |

## Execution Order

1. **Global input guardrails** run on the user message.
2. If all pass (or warn), the supervisor routes to agent(s).
3. **Per-agent input guardrails** run when each agent is activated.
4. The agent processes the query (RAG, tools, LLM).
5. **Global output guardrails** run on the final response.
6. The response is returned to the user.

## Configuration Example

```yaml
# Global guardrails
guardrails:
  input:
    - type: prompt_injection
      fail_action: block
    - type: content_safety
      fail_action: block
    - type: max_length
      fail_action: block
      config:
        max_characters: 5000
  output:
    - type: pii_detection
      fail_action: redact
      config:
        entities: [email, phone, credit_card]

agents:
  venue-navigator:
    guardrails:
      input:
        - type: topic_restriction
          fail_action: warn
          config:
            allowed_topics: [room, venue, floor, zone, direction, entrance]

  schedule-content:
    guardrails:
      input:
        - type: topic_restriction
          fail_action: warn
          config:
            allowed_topics: [schedule, session, talk, keynote, speaker, track]
```

## Best Practices

- **Use `block` for safety-critical guardrails** (prompt injection, content safety).
- **Use `warn` for topic restrictions** — users may phrase things unexpectedly, and blocking them outright can be frustrating.
- **Use `redact` for PII** — preserves the response while protecting sensitive data.
- **Keep `allowed_topics` focused** — 10–15 keywords per agent is a good range. Too few and legitimate queries get flagged; too many and the guardrail loses effectiveness.
- **Test guardrails with edge cases** — ensure they catch real threats without blocking legitimate queries.
