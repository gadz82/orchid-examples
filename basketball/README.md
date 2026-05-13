# Basketball Demo — Hello World Example

The **basketball demo** is Orchid's minimal end-to-end example. It wires two `GenericAgent` instances — an NBA stats expert and a sports psychologist — using only built-in tools defined in YAML and a SQLite storage backend. No MCP servers, no external APIs, and no custom Python agent classes are required.

## What It Demonstrates

- **GenericAgent with built-in tools** — Two agents (`basketball` and `psychologist`) with tools declared entirely in YAML (`get_player_stats`, `get_team_stats`, `assess_mental_state`, `suggest_intervention`)
- **Cross-agent skills** — The `basketball` agent can invoke the `psychologist` agent's skills for player mental state analysis
- **SQLite persistence** — Custom file-based SQLite storage at `/data/chats.db` with migrations
- **Local LLM via Ollama** — Uses `ollama/llama3.2` for completions and `ollama/nomic-embed-text` for embeddings
- **Supervisor routing** — LangGraph supervisor automatically routes queries to the appropriate agent based on content and available tools
- **Dev auth bypass** — `auth.dev_bypass: true` for local development without OAuth setup

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Agent definition | `GenericAgent` via YAML only |
| Tools | Built-in Python functions with `@tool` decorator |
| Storage | Custom `OrchidSQLiteChatStorage` subclass |
| LLM | Ollama (`llama3.2`, `nomic-embed-text`) |
| Auth | Development bypass mode |
| RAG | Qdrant backend (optional, not indexed in demo) |

## Prerequisites

- Ollama running with models:
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ollama pull minicpm-v
  ```
- Python 3.11+ with `orchid-ai` and `orchid-cli` installed

## Usage

### Via Docker Compose (recommended)

```bash
# From repo root
docker compose -f docker-compose.demo.yml up --build
```

This starts the API, Qdrant, and Ollama together.

### Via Standalone API

```bash
pip install -e orchid -e orchid-api
ORCHID_CONFIG=examples/basketball/orchid.yml uvicorn orchid_api.main:app --port 8000
```

### Via CLI

```bash
pip install -e orchid -e orchid-cli

# Interactive session
orchid chat interactive --config examples/basketball/orchid.yml

# Single message
orchid chat send "Tell me about LeBron James" \
  --config examples/basketball/orchid.yml

# Ask the psychologist
orchid chat send "How can LeBron improve his mental resilience?" \
  --agent psychologist \
  --config examples/basketball/orchid.yml
```

## File Layout

```
examples/basketball/
├── orchid.yml              # Top-level config (LLM, storage, RAG)
├── agents.yaml             # Agent definitions (basketball, psychologist)
├── identity.py             # Dev identity resolver (bypass mode)
├── storage/
│   ├── __init__.py
│   └── sqlite.py           # Custom SQLite chat storage implementation
├── tools/
│   ├── __init__.py
│   ├── basketball.py       # get_player_stats, get_team_stats
│   └── psychology.py       # assess_mental_state, suggest_intervention
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_morning_trivia_e2e.py  # End-to-end test
```

## Sample Interaction

```
User: Tell me about LeBron James
Assistant: [calls get_player_stats tool]
LeBron James has played 21 seasons, averaging 27.2 PPG, 7.5 RPG, 7.4 APG...

User: How is his mental game?
Assistant: [routes to psychologist agent]
[psychologist calls assess_mental_state]
LeBron demonstrates exceptional mental resilience, particularly in high-pressure...
```

## Storage Backend

The example uses a custom SQLite storage backend at `examples/basketball/storage/sqlite.py`. This demonstrates how to implement `OrchidChatStorage` for integrators who need custom persistence (e.g., existing databases, multi-tenant schemas, or compliance requirements).

Key methods implemented:
- `create_chat()` / `delete_chat()`
- `list_chats()`
- `save_message()` / `load_messages()`
- `migrate()` — applies schema migrations from `storage/migrations/`

## Contrast with Other Examples

| Example | Complexity | Custom Code | External Deps |
|---------|-----------|-------------|---------------|
| **basketball** | Minimal | SQLite storage + 4 tools | Ollama only |
| helpdesk | Medium | Event-driven workflow | Ollama + Postgres |
| restaurant | Medium | Custom agent class | Ollama + Qdrant |
| mcp-auth | Advanced | None (YAML-only) | 3 MCP servers |

## Next Steps

After exploring the basketball demo, try:
- **recipes** — Zero-infrastructure RAG with ChromaDB
- **helpdesk** — Event-driven workflows with Pollen + Bloom
- **mcp-auth** — MCP server authentication patterns
