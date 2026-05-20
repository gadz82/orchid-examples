<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, and codebase analysis -->

# Runtime

`OrchidRuntime` is the single integration point for consumers who want to programmatically build and use the Orchid graph. It holds all resolved dependencies needed by `build_graph()` — override only what you need, everything else gets a sensible default.

## OrchidRuntime

**File:** `orchid_ai/__init__.py` (exported from the package root)

```python
from orchid_ai import OrchidRuntime, build_graph, load_config

config = load_config("agents.yaml")
runtime = OrchidRuntime(default_model="ollama/llama3.2")
graph = build_graph(config=config, runtime=runtime)
```

### Fields

| Field | Type | Default |
|-------|------|---------|
| `default_model` | `str` | `"ollama/llama3.2"` |
| `reader` | `OrchidVectorReader \| None` | `NullVectorReader` (no RAG) |
| `llm_service` | `LLMProvider \| None` | `LiteLLMProvider()` |
| `mcp_client_factory` | `MCPClientFactory \| None` | `StreamableHttpMCPClient` factory |
| `chat_model` | `BaseChatModel \| None` | `build_chat_model(default_model)` |
| `chat_storage` | `OrchidChatStorage \| None` | `None` (configured via orchid.yml) |

### Minimal (All Defaults)

Uses `LiteLLMProvider` for LLM, `NullVectorReader` (no RAG), and `StreamableHttpMCPClient` for MCP servers:

```python
config = load_config("agents.yaml")
runtime = OrchidRuntime(default_model="ollama/llama3.2")
graph = build_graph(config=config, runtime=runtime)
```

### Custom Vector Store

Plug in a Qdrant-backed reader:

```python
from orchid_ai.rag.factory import build_reader

reader = build_reader(
    vector_backend="qdrant",
    qdrant_url="http://localhost:6333",
    embedding_model="ollama/nomic-embed-text",
)

runtime = OrchidRuntime(
    default_model="gemini/gemini-2.5-flash",
    reader=reader,
)
```

### Custom LLM Provider

Replace the default `LiteLLMProvider` with your own implementation:

```python
from orchid_ai.core.llm_provider import LLMProvider

class MyProvider(LLMProvider):
    async def complete(self, *, model: str, messages: list, temperature: float = 0.2) -> str:
        # Your custom logic
        ...

runtime = OrchidRuntime(
    default_model="my-model",
    llm_service=MyProvider(),
)
```

### Custom MCP Client Factory

Control how MCP clients are created from server config entries:

```python
runtime = OrchidRuntime(
    default_model="ollama/llama3.2",
    mcp_client_factory=lambda cfg: MyMCPClient(cfg.url, api_key=MY_KEY),
)
```

### All Options

```python
runtime = OrchidRuntime(
    default_model="openai/gpt-4o",
    reader=my_qdrant_reader,
    llm_service=MyCustomProvider(),
    mcp_client_factory=my_factory,
)
graph = build_graph(config=config, runtime=runtime)
```

## build_graph()

**File:** `orchid_ai/graph/graph.py`

The `build_graph()` factory assembles the LangGraph from the loaded configuration and runtime:

```python
from orchid_ai import build_graph, load_config, OrchidRuntime

config = load_config("agents.yaml")
runtime = OrchidRuntime(default_model="ollama/llama3.2")
graph = build_graph(config=config, runtime=runtime)
```

### What It Does

1. **Resolves dependencies** — Uses the runtime to get the LLM, reader, MCP client factory.
2. **Builds agents** — Creates `GenericAgent` instances (or custom agent classes) from the configuration.
3. **Wires the supervisor** — Creates the routing and synthesis nodes with configured prompts.
4. **Registers tools** — Imports built-in tool handlers via `importlib`.
5. **Connects MCP servers** — Creates MCP client instances for each configured server.
6. **Builds the LangGraph** — Assembles all nodes and edges into a compilable graph.

### Graph Structure

```
START → supervisor_routing → [parallel/sequential agents] → supervisor_synthesis → END
```

For skills, intermediate nodes are added for each skill step.

## load_config()

**File:** `orchid_ai/config/loader.py`

Loads and validates an `agents.yaml` file:

```python
from orchid_ai import load_config

config = load_config("agents.yaml")
```

Returns an `OrchidAgentsConfig` Pydantic model. Validation errors are raised if the YAML is malformed or contains invalid keys (all models use `extra="forbid"`).

## Embedded API Pattern

Orchid can be embedded in an existing FastAPI application:

```python
from fastapi import FastAPI
from orchid_ai import OrchidRuntime, build_graph, load_config

app = FastAPI()

@app.on_event("startup")
async def startup():
    config = load_config("agents.yaml")
    runtime = OrchidRuntime(default_model="openai/gpt-4o")
    app.state.graph = build_graph(config=config, runtime=runtime)

@app.post("/chat")
async def chat(message: str):
    result = await app.state.graph.ainvoke({
        "messages": [{"role": "user", "content": message}],
    })
    return result
```

## Dependency Injection

The runtime uses dependency injection — each field is optional and has a sensible default. Integrators override only what they need:

- **No RAG?** Don't set `reader` — `NullVectorReader` is used.
- **No MCP?** Don't configure `mcp_servers` in agents.yaml — no MCP clients are created.
- **Custom LLM?** Set `llm_service` or `chat_model` — the factory is bypassed.
- **Custom storage?** Set `chat_storage` in the API/CLI lifespan.

This makes Orchid flexible: it works out of the box with defaults, but every component is replaceable.
