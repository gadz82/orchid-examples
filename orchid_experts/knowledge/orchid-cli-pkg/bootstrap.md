<!-- Source: derived from orchid-cli/AGENTS.md, orchid-website/src/content/packages/orchid-cli.mdx, and codebase analysis -->

# Bootstrap

The CLI bootstrap process mirrors the API's lifespan — loading configuration, building the graph, and initializing dependencies — but adapted for a CLI context where there's no HTTP server and no long-running process.

## Bootstrap Flow

The `bootstrap.py` module orchestrates initialization:

1. **Load Configuration** — Reads `orchid.yml` (for runtime settings) and `agents.yaml` (for agent definitions). Both are validated by Pydantic at load time.
2. **Resolve Identity** — Creates the identity resolver class from the `identity_resolver_class` dotted path via `importlib`.
3. **Setup Storage** — Initializes chat storage (SQLite by default, `:memory:` for one-off commands, file-based for interactive mode). Runs database migrations on `init_db()`.
4. **Build Vector Reader** — Creates the vector reader. Uses ChromaDB by default (zero-infra local), Qdrant if configured in `orchid.yml`.
5. **Warm MCP Capabilities** — Proactively discovers tools from `auth.mode: none` MCP servers at bootstrap time.
6. **Run Startup Hooks** — Seeds knowledge files into the vector store, runs custom hooks.
7. **Build Graph** — Compiles the LangGraph from the loaded configuration and runtime.

## Shared Bootstrap

The bootstrap logic is shared between CLI and API via a common initialization path. Both use the same configuration files and produce the same graph:

```python
from orchid_cli.bootstrap import bootstrap_orchid

async with bootstrap_orchid(config_path="orchid.yml") as ctx:
    # ctx.graph — compiled LangGraph
    # ctx.auth_context — resolved OrchidAuthContext
    # ctx.reader — vector reader (or NullVectorReader)
    # ctx.chat_storage — chat persistence backend
    # ctx.mcp_clients — warmed MCP clients

    result = await ctx.graph.ainvoke({
        "messages": [{"role": "user", "content": "Hello!"}],
        "auth_context": ctx.auth_context,
    })
```

The async context manager handles setup and teardown.

## CLI Defaults

The CLI uses developer-friendly defaults:

- **LLM model:** `ollama/llama3.2` (local, free).
- **Vector backend:** ChromaDB (stored in `~/.orchid/chromadb/`).
- **Storage:** SQLite (in-memory for `orchid chat send`, file-based for `orchid chat interactive`).
- **Auth:** `dev_bypass: false` with a trivial resolver that accepts any token.

## Configuration Resolution

```
environment variables > orchid.yml > CLI defaults
```

This means:
- `orchid.yml` overrides CLI defaults.
- Environment variables override `orchid.yml`.
- Command-line flags (`--config`, `--model`) override everything for that invocation.

## Auth Context

For interactive mode and one-off commands, the CLI creates a synthetic `OrchidAuthContext`:

```python
auth_context = OrchidAuthContext(
    access_token="cli-token",
    tenant_key="default",
    user_id="cli-user",
)
```

For OAuth-enabled CLIs (after `orchid auth login`), the auth context comes from the stored OAuth tokens in `~/.orchid/tokens.json`.

## Runtime Injection

The bootstrap builds an `OrchidRuntime` with the configured dependencies:

```python
runtime = OrchidRuntime(
    default_model="ollama/llama3.2",
    reader=chroma_reader,              # ChromaDB or Qdrant
    chat_storage=sqlite_storage,        # In-memory or file-based
    mcp_client_factory=None,           # StreamableHttpMCPClient default
)
graph = build_graph(config=config, runtime=runtime)
```

### Override Points

When using the CLI programmatically:

```python
from orchid_ai import OrchidRuntime, build_graph, load_config

config = load_config("agents.yaml")
runtime = OrchidRuntime(
    default_model="openai/gpt-4o",       # Override model
    reader=my_qdrant_reader,              # Override vector store
    llm_service=my_custom_provider(),      # Override LLM
)
graph = build_graph(config=config, runtime=runtime)
```
