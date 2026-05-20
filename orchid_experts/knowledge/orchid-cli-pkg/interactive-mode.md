<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# Interactive Mode

The CLI's interactive mode provides a rich terminal UI for multi-turn conversations with agents.

## Starting Interactive Mode

```bash
orchid chat interactive --config examples/orchid_experts/orchid.yml
```

## Slash Commands

In interactive mode, type `/` to access commands:

| Command | Action |
|---------|--------|
| `/agents` | List available agents and their descriptions |
| `/skills` | List available cross-agent skills |
| `/agent NAME` | Route subsequent messages to a specific agent |
| `/new` | Start a new chat session |
| `/history` | Show the current conversation history |
| `/help` | Show available commands |
| `/exit` or `/quit` | Exit interactive mode |
| `/clear` | Clear the screen |

## Rich UI

The CLI uses the `rich` library for formatted output:

- **Agent routing** — Shows which agent was selected for each query.
- **Tool calls** — Displays MCP and built-in tool calls with arguments.
- **RAG context** — Shows retrieved document sources.
- **Error display** — Formatted error messages with suggestions.

## Conversation Management

Interactive mode maintains conversation state:

- Chat history is persisted to SQLite (file-based, not in-memory).
- Use `/new` to start a new chat without losing the old one.
- Previous chats can be resumed with `orchid chat interactive --chat-id <id>`.

## Response Streaming

Responses stream token-by-token to the terminal:

```
You: What is the GenericAgent pipeline?

orchid-framework Agent:
The GenericAgent pipeline is a 6-step process in Orchid...[streaming tokens]

▸ Step 1: RAG Retrieval
▸ Step 2: Skill Detection
▸ Step 3: MCP Tool Calls
▸ Step 4: Built-in Tool Calls
▸ Step 5: Dynamic RAG Injection
▸ Step 6: LLM Summarization
```

## Configuration

Interactive mode respects the `orchid.yml` configuration:

- LLM model selection.
- Vector backend (Qdrant or ChromaDB).
- Storage backend (SQLite by default).
- Guardrails (active during interactive sessions).
