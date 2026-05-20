<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# Chat Components

The frontend's chat UI is composed of reusable React components that handle message display, input, streaming, and special interaction patterns. Each component follows the existing component conventions from the Next.js App Router architecture.

## Sidebar

Displays the list of chat sessions with navigation:

```tsx
<ChatSidebar chats={chatList} activeChatId="chat-123" />
```

Features:
- **Chat list** — Titles and relative timestamps ("2 hours ago").
- **Active chat highlighting** — The current chat is visually distinct.
- **New chat button** — Creates a new chat and navigates to it.
- **Delete chat** — With confirmation dialog ("Are you sure?").
- **Search** — Filter chats by title (optional, for many chats).
- **Loading state** — Skeleton placeholders while chats load.
- **Empty state** — "No chats yet. Start a new conversation."

## ChatInput

Message input with integrated file upload:

```tsx
<ChatInput
  chatId="chat-123"
  disabled={isStreaming}
  placeholder="Ask the Orchid experts..."
/>
```

Features:
- **Text input** — Enter to send, Shift+Enter for newline.
- **Drag-and-drop** — Drop files directly into the input area.
- **File attachment preview** — Shows file name and size before sending.
- **Remove attachment** — Click X on the file preview to remove.
- **Send button** — Disabled state while streaming.
- **Character count** — Optional display when approaching limits.
- **Keyboard shortcuts** — `/` to focus input, `Escape` to blur.

The input area expands as the user types (up to a max height), then scrolls.

## MessageBubble

Renders individual chat messages with rich formatting:

```tsx
<MessageBubble
  role="assistant"
  content="# Hello\n\nThis is a **markdown** response."
  agentsUsed={["orchid-framework"]}
  metadata={{ origin: "agent" }}
/>
```

Features:
- **Role-based styling** — User messages right-aligned (blue), assistant messages left-aligned (gray).
- **Agent attribution badges** — Shows which agents contributed to the response.
- **Markdown rendering** — Headers, bold, italic, lists, tables.
- **Code blocks** — Syntax highlighting for Python, YAML, TypeScript, Bash, JSON.
- **Source citations** — When RAG is used, shows source documents.
- **Tool call indicators** — Shows "🛠 Called: search_catalog" when tools were used.
- **Bloom badge** — Messages with `metadata.origin: "bloom"` get a distinct indicator.

### Message Loading States

```tsx
{isStreaming && <ThinkingDots />}  // Animated dots while waiting
{hasError && <ErrorMessage error={error} onRetry={retry} />}
```

## HITLCard (Human-in-the-Loop)

Displays when an agent calls a tool with `requires_approval: true`:

```tsx
<HITLCard
  toolName="create_order"
  toolArgs={{ itemId: "SKU-123", quantity: 1, total: "$29.99" }}
  onApprove={() => resume("approved")}
  onReject={() => resume("rejected")}
/>
```

Features:
- **Tool name and arguments** — Displayed clearly for user review.
- **Approve/Reject buttons** — With color coding (green approve, red reject).
- **Timeout** — If no response within configurable timeout, the graph continues with default behavior.
- **Resume** — Sends the decision to `PATCH /chats/{id}/resume`.

## MiniAgentTrace

Shows mini-agent decomposition and execution progress:

```tsx
<MiniAgentTrace
  decisions={{
    should_fork: true,
    sub_tasks: [
      { id: "1", instruction: "Analyze Q3 revenue", status: "completed" },
      { id: "2", instruction: "Analyze Q3 growth", status: "completed" },
      { id: "3", instruction: "Generate comparison chart", status: "running" },
    ],
  }}
/>
```

Displays:
- **Decomposition** — How the query was split into sub-tasks.
- **Per-task status** — Pending, running, completed, failed (with color icons).
- **Parallel execution indicator** — Shows that tasks ran simultaneously.
- **Aggregation progress** — When all tasks complete, shows "Aggregating results..."

### Integration with SSE

Mini-agent trace updates arrive via SSE events:

```
event: mini_agent.decomposed
data: {"tasks": [...]}

event: mini_agent.started
data: {"mini_id": "1"}

event: mini_agent.finished
data: {"mini_id": "1", "result": "..."}

event: mini_agent.aggregated
data: {"final_result": "..."}
```

The `MiniAgentTrace` component subscribes to these events and updates in real-time, giving users visibility into complex parallel agent executions.
