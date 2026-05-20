<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# Streaming Proxy

The frontend proxies SSE (Server-Sent Events) streams from the API through Next.js server actions to provide real-time token-by-token responses in the browser. This architecture keeps bearer tokens out of client-side JavaScript while enabling responsive streaming UX.

## Architecture

```
Orchid API (SSE endpoint) → Server Action (Next.js) → Browser (EventSource-like)
   GET /chats/{id}/stream       ReadableStream           useChatStream hook
```

1. Browser calls a server action to start streaming (with session cookie, not bearer token).
2. Server action opens an SSE connection to the API (with server-side bearer token).
3. Server action creates a `ReadableStream` and pipes SSE events through.
4. Browser's `useChatStream` hook reads the stream and updates React state.

## useChatStream Hook

The primary interface for consuming streams in components:

```tsx
import { useChatStream } from "@/lib/use-chat-stream";

function ChatPage({ chatId }: { chatId: string }) {
  const { messages, isStreaming, error, send } = useChatStream(chatId);

  async function handleSend(text: string) {
    await send(text);  // Triggers SSE stream behind the scenes
  }

  return (
    <div>
      <MessageList messages={messages} isStreaming={isStreaming} />
      <ChatInput onSend={handleSend} disabled={isStreaming} />
      {error && <ErrorBanner message={error} />}
    </div>
  );
}
```

### Hook States

- **idle** — No active stream. Input is enabled.
- **streaming** — Messages arriving in real-time. Input is disabled, streamed content updates live.
- **error** — Stream encountered an error. Error message displayed, input re-enabled.
- **done** — Stream completed. Final message rendered, input re-enabled.

## SSE Event Handling

The hook parses SSE events and updates the message list:

| Event | UI Update |
|-------|-----------|
| `agent.token` | Append token to the current streaming message. |
| `agent.tool_call` | Show "🛠 Calling: tool_name..." indicator. |
| `agent.tool_result` | Append tool result to message context. |
| `agent.start` | Create a new message bubble for this agent. |
| `agent.done` | Mark agent message as complete. |
| `supervisor.routing` | Show "Routing to: agent1, agent2..." in UI. |
| `supervisor.synthesis` | Show "Synthesizing response..." indicator. |
| `error` | Display error in the chat. |
| `done` | Mark turn as complete, re-enable input. |

## Token Proxy Pattern

The streaming proxy is the key to keeping tokens secure:

```typescript
// src/app/actions.ts
"use server";

import { auth } from "@/lib/auth";

export async function streamChat(chatId: string, message: string) {
  const session = await auth();
  // Server-side only — bearer token never reaches the browser

  const response = await fetch(`${API_URL}/chats/${chatId}/stream`, {
    headers: {
      Authorization: `Bearer ${session.accessToken}`,
      Accept: "text/event-stream",
    },
  });

  // Return the raw ReadableStream to the browser
  return new Response(response.body, {
    headers: { "Content-Type": "text/event-stream" },
  });
}
```

The browser receives only the SSE events, not the bearer token.

## Reconnection

SSE connections can drop. The hook implements automatic reconnection:

```typescript
// Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
const backoff = Math.min(1000 * Math.pow(2, attempts), 30000);
```

On reconnect, the hook sends the `Last-Event-Id` header so the API can resume from where the connection dropped. This prevents missing tokens during reconnection.

### Connection States

- **Connected** — Streaming normally.
- **Reconnecting** — Connection dropped, retrying. Shows "Reconnecting..." indicator.
- **Failed** — Max retries exceeded. Shows error with manual retry button.
- **Closed** — User navigated away, connection intentionally closed.

## Error Handling

Stream errors are surfaced in the UI:

```tsx
{error && (
  <ErrorBanner
    message={error.message}
    onRetry={() => reconnect()}
    onDismiss={() => clearError()}
  />
)}
```

Common stream errors:
- **401 Unauthorized** — Session expired. Redirect to login.
- **500 Internal Error** — API error. Show retry button.
- **Connection timeout** — Network issue. Auto-reconnect.
- **Rate limit** — Too many requests. Show "Please wait..." with countdown.
