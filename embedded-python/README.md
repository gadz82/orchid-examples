# Embedded Python — calling Orchid from any Python code

Use **`Orchid`** when you want to invoke the agent graph directly
from a Django view, a Celery task, a background worker, a notebook, or a
one-off script — no HTTP, no CLI.  The client owns the full lifecycle:
loads `orchid.yml`, builds the reader, chat storage, MCP token store,
optional checkpointer, and compiled graph.

## Files

| File | What it shows |
|------|---------------|
| `orchid.yml` | Shared config that points at the restaurant agents |
| `01_minimal.py` | One request, one response |
| `02_multi_turn.py` | Same `chat_id` across turns — history auto-loaded |
| `03_streaming.py` | Token-level streaming via `client.stream(...)` |
| `04_hitl.py` | Pause / resume flow for tool approvals |
| `05_custom_runtime.py` | Bring your own `OrchidRuntime` (low-level) |
| `06_inline_config.py` | Build agents + tools entirely in Python (no YAML) |

## Running

From the repo root:

```bash
# Simple one-shot
python -m examples.embedded-python.01_minimal

# Multi-turn (same chat_id reused)
python -m examples.embedded-python.02_multi_turn

# Streaming tokens
python -m examples.embedded-python.03_streaming

# HITL pause / resume (requires the agent config to mark a tool as requires_approval)
python -m examples.embedded-python.04_hitl

# Custom OrchidRuntime, no persistence
python -m examples.embedded-python.05_custom_runtime

# Fully in-code config — no YAML files anywhere
python -m examples.embedded-python.06_inline_config
```

Qdrant and the LLM provider (e.g. Ollama, OpenAI, Gemini) must be
reachable from the process running these scripts.

## The public surface

```python
from orchid_ai import Orchid, OrchidInvokeResult, OrchidPendingApproval
```

### Construction

```python
# Highest-level — loads everything from orchid.yml and owns resources:
async with Orchid.from_config_path("orchid.yml") as client:
    ...

# Low-level — you own the runtime + (optional) chat_repo:
client = Orchid(config=config, runtime=runtime)
try:
    ...
finally:
    await client.close()
```

### Invocation

```python
result: OrchidInvokeResult = await client.invoke(
    message,
    chat_id=...,          # reuse to continue a conversation (history auto-loaded)
    user_id="alice",
    tenant_id="acme",
    access_token="...",   # forwarded to MCP servers (passthrough mode)
    auth=...,             # or pass a fully-formed OrchidAuthContext instead
    history=...,          # or pass explicit history (no persistence lookup)
    persist=True,         # save user+assistant messages to chat_repo
)
```

### Streaming

```python
async for mode, chunk in client.stream(message, user_id=..., stream_mode="messages"):
    # chunk semantics follow LangGraph's astream modes
    ...
```

### Human-in-the-loop

When an agent tool is flagged with `requires_approval: true` in
`agents.yaml`, `invoke()` returns with `result.interrupted == True`.
Collect a decision, then:

```python
await client.resume(chat_id, approved=True)
```

A checkpointer must be configured (`checkpointer:` section in `orchid.yml`,
or `checkpointer_type=` kwarg on `from_config_path`) for resume to work —
without it the pause state cannot be persisted between calls.

## When to use this vs the other entry points

- **`Orchid`** — in-process Python, no HTTP boundary.  Best for
  background jobs, Django views, notebooks, CLIs that embed orchid.
- **`orchid-api` (FastAPI)** — when other services / browsers need HTTP
  access.  Use directly (`orchid_api.main:app`) or mount its routers
  into your existing FastAPI app (see `examples/embedded-api/`).
- **`orchid-cli`** — interactive terminal use or shell scripts.

All three share the same underlying runtime.  Switching between them is
a matter of which adapter you expose.
