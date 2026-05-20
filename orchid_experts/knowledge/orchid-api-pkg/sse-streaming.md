<!-- Source: derived from orchid-api/AGENTS.md, orchid-website/src/content/packages/orchid-api.mdx, and codebase analysis -->

# SSE Streaming

Orchid uses Server-Sent Events (SSE) for real-time streaming of chat responses and Bloom run progress. The streaming router manages SSE connections and emits lifecycle events.

## Chat Streaming

```
GET /chats/{chat_id}/stream
Accept: text/event-stream
```

### Event Vocabulary

| Event | Description |
|-------|-------------|
| `agent.start` | An agent has started processing. |
| `agent.token` | A token from the agent's LLM response. |
| `agent.tool_call` | The agent is calling a tool. |
| `agent.tool_result` | Tool call result received. |
| `agent.done` | Agent finished processing. |
| `supervisor.routing` | Supervisor is routing the query. |
| `supervisor.synthesis` | Supervisor is synthesizing results. |
| `error` | An error occurred. |
| `done` | The entire turn is complete. |

### Example Stream

```
event: supervisor.routing
data: {"agents": ["search", "catalog"]}

event: agent.start
data: {"agent": "search"}

event: agent.token
data: {"agent": "search", "token": "I"}

event: agent.token
data: {"agent": "search", "token": " found"}

event: agent.done
data: {"agent": "search", "result": "..."}

event: done
data: {}
```

## Bloom Streaming

```
GET /events/stream
```

### Bloom Events

| Event | Description |
|-------|-------------|
| `job_run.started` | A Bloom run has started. |
| `job_run.progress` | Run progress update. |
| `job_run.completed` | Run completed successfully. |
| `job_run.failed` | Run failed. |
| `mini_agent.decomposed` | Mini-agent query decomposed. |
| `mini_agent.started` | Mini-agent started. |
| `mini_agent.finished` | Mini-agent completed. |
| `mini_agent.aggregated` | Mini-agent results aggregated. |

### Visibility Filter

Bloom events are filtered by visibility: only users with appropriate access see the events. The filter uses the `visibility` level from the trigger configuration.

## Connection Management

- SSE connections are kept alive with periodic heartbeats.
- Disconnected clients are detected and cleaned up.
- Multiple clients can stream the same chat simultaneously.
- Bloom streaming is separate from chat streaming — different endpoints, same event vocabulary for shared events.

## Frontend Integration

The frontend consumes SSE via the `use-chat-stream` hook which wraps the SSE proxy server action.
