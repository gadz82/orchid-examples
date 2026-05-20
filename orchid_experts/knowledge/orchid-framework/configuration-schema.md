<!-- Source: derived from orchid/README.md, orchid-website/src/content/configuration-reference/agents.mdx, orchid-website/src/content/configuration-reference/infrastructure.mdx, and codebase analysis -->

# Configuration Schema

Orchid uses two configuration files that work together: `agents.yaml` (agent definitions) and `orchid.yml` (runtime settings). Both are validated by Pydantic models at load time.

## Two-File Architecture

### agents.yaml

Managed by the library. Defines agents, tools, skills, supervisor, and guardrails. Loaded via `load_config(path)` which validates against `OrchidAgentsConfig`.

### orchid.yml

Managed by orchid-api and orchid-cli. Defines runtime settings: LLM model, RAG backend, storage, auth, and tracing. Each nested YAML key maps to a flat environment variable.

**Priority:** env vars > `orchid.yml` > hardcoded defaults.

## agents.yaml Root Structure

```yaml
version: "1"

defaults:
  llm:
    model: "ollama/llama3.2"
    temperature: 0.2
    fallback_model: null
  rag:
    k: 5
    enabled: true
    rag_ttl: 0

tools:
  my-tool:
    handler: myapp.tools.my_tool
    description: "What this tool does"

skills:
  my-skill:
    description: "When to activate this skill"
    steps:
      - agent: agent-a
        instruction: "Do something"
      - agent: agent-b
        instruction: "Then do something else"

supervisor:
  assistant_name: "My Assistant"
  history_max_turns: 20
  history_max_chars: 1000

guardrails:
  input: [...]
  output: [...]

agents:
  agent-a:
    description: "..."
    prompt: "..."
    rag:
      namespace: ns-a
      k: 5
```

## Key Configuration Sections

### version

Schema version string. Currently always `"1"`. Reserved for future backward-compatible migrations.

### defaults

Default LLM and RAG settings inherited by every agent. Agents can override any default individually.

- **`defaults.llm.model`** — LiteLLM-format model identifier (e.g., `ollama/llama3.2`, `openai/gpt-4o`). Default: `"gemini/gemini-2.5-flash"`.
- **`defaults.llm.temperature`** — Randomness control (0.0–1.0). Default: `0.2`.
- **`defaults.llm.fallback_model`** — Optional fallback model for automatic retry on 503/timeout. Default: `null`.
- **`defaults.rag.k`** — Max documents retrieved per query. Default: `5`.
- **`defaults.rag.enabled`** — Master RAG switch. Default: `true`.
- **`defaults.rag.rag_ttl`** — Default TTL for tool results cached in RAG (0 = disabled). Default: `0`.

### tools

Global registry of built-in Python tools. Each tool maps a name to a Python function via dotted import path.

- **`handler`** — Dotted Python import path (required). Imported via `importlib` at graph build time.
- **`description`** — Human-readable description for the LLM.
- **`parameters`** — Optional parameter declarations that override auto-extracted function signatures.
- **`inject_to_rag`** — Store tool results in vector store for future retrieval. Default: `false`.
- **`rag_ttl`** — Per-tool RAG cache TTL in seconds.

### skills

Orchestrator-level (cross-agent) multi-step workflows. The supervisor detects skill triggers via the `description` field.

- **`description`** — When to activate this skill.
- **`steps`** — Ordered list of `{agent, instruction}` pairs.

### supervisor

Customization of the supervisor node.

- **`assistant_name`** — Name used in synthesized responses. Default: `"AI assistant"`.
- **`routing_system_prompt`** — Custom routing prompt. Default: built-in template.
- **`synthesis_system_prompt`** — Custom synthesis prompt. Default: built-in template.
- **`history_max_turns`** — Max conversation pairs in supervisor context. Default: `20`.
- **`history_max_chars`** — Max characters per message in history. Default: `1000`.
- **`history_summary_enabled`** — Enable sliding-window summarization. Default: `true`.
- **`history_summary_model`** — Model for summarization (use cheap/fast). Default: `null` (uses supervisor model).
- **`history_summary_recent_turns`** — Recent turns kept verbatim. Default: `10`.

### guardrails

Global input and output guardrail chains.

- **Input guardrails** run on every user message before the supervisor.
- **Output guardrails** run on every response before returning to the user.

Types: `prompt_injection`, `content_safety`, `max_length`, `pii_detection`, `topic_restriction`, `groundedness`.

### agents

Dictionary of agent definitions keyed by name. Each agent has:

- **`description`** — For supervisor routing (required).
- **`prompt`** — System prompt for the LLM (required).
- **`class`** — Dotted import path for custom `OrchidAgent` subclass. Default: `null` (uses `GenericAgent`).
- **`llm`** — Per-agent LLM override.
- **`rag`** — Per-agent RAG settings (`namespace`, `k`, `enabled`, `rag_ttl`).
- **`tools`** — List of built-in tool names.
- **`mcp_servers`** — List of MCP server connections.
- **`guardrails`** — Per-agent input/output guardrails.
- **`execution_hints`** — Hints for the supervisor (`parallel_safe`).

## orchid.yml Structure

```yaml
agents:
  config_path: path/to/agents.yaml

llm:
  model: ollama/llama3.2
  ollama_api_base: http://host.docker.internal:11434

auth:
  dev_bypass: false
  identity_resolver_class: myproject.identity.MyResolver

rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text

upload:
  vision_model: ollama/minicpm-v
  namespace: uploads
  max_size_mb: 20
  chunk_size: 1000
  chunk_overlap: 200

storage:
  class: myproject.storage.MyChatStorage
  dsn: /data/chats.db

startup:
  hook: myproject.hooks.seed_knowledge

tracing:
  langsmith_tracing: false
```

## Validation

Both files are validated at load time:

```python
from orchid_ai import load_config

config = load_config("agents.yaml")  # Validates against OrchidAgentsConfig
```

The CLI provides a validation command:

```bash
orchid config validate agents.yaml
```

All Pydantic models use `extra="forbid"` — typos in keys surface as clear errors instead of silent drift.
