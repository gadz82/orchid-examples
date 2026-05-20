<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, orchid-website/src/content/concepts/multi-llm.mdx, and codebase analysis -->

# Multi-LLM Support

Orchid is provider-agnostic for LLM inference. It uses LangChain's `BaseChatModel` as its LLM abstraction, with a factory function that creates models from LiteLLM-style model strings. This means you can use any LLM provider supported by LiteLLM without changing your agent code.

## Model String Format

Model identifiers use the `provider/model-name` format:

```
ollama/llama3.2
openai/gpt-4o
anthropic/claude-sonnet-4-20250514
gemini/gemini-2.5-flash
groq/llama-3.3-70b-versatile
```

The provider prefix tells the factory which provider-specific package to use. If the provider package is installed, it is used directly; otherwise, the factory falls back to `ChatLiteLLM` which routes through the `litellm` library.

## build_chat_model() Factory

**File:** `llm_factory.py`

```python
from orchid_ai.llm_factory import build_chat_model

model = build_chat_model("openai/gpt-4o")
```

The factory:

1. Parses the model string to extract the provider and model name.
2. Checks if a provider-specific LangChain package is installed (e.g., `langchain-openai` for `openai/`).
3. If available, creates the provider-specific model directly (better performance, fewer dependencies).
4. Falls back to `ChatLiteLLM` which routes through the `litellm` library.

### Provider Priority

| Provider | Package | Fallback |
|----------|---------|----------|
| `openai/` | `langchain-openai` | `ChatLiteLLM` |
| `anthropic/` | `langchain-anthropic` | `ChatLiteLLM` |
| `google/` | `langchain-google-genai` | `ChatLiteLLM` |
| `groq/` | `langchain-groq` | `ChatLiteLLM` |
| `ollama/` | `langchain-ollama` | `ChatLiteLLM` |

## Per-Agent Model Configuration

Each agent can use a different LLM model:

```yaml
defaults:
  llm:
    model: "ollama/llama3.2"
    temperature: 0.2

agents:
  fast-agent:
    description: "Simple questions agent"
    prompt: "You answer simple questions quickly."
    # Inherits defaults: ollama/llama3.2

  smart-agent:
    description: "Complex reasoning agent"
    prompt: "You handle complex reasoning tasks."
    llm:
      model: "openai/gpt-4o"
      temperature: 0.1
    # Overrides: uses GPT-4o instead of default
```

This allows you to assign cheaper/faster models to simple agents and more capable models to complex ones, optimizing cost and latency.

## Fallback Models

Orchid supports automatic fallback to a secondary model when the primary model fails (503, rate limit, timeout):

```yaml
defaults:
  llm:
    model: "openai/gpt-4o"
    fallback_model: "ollama/llama3.2"
```

When the primary model fails, the framework automatically retries with the fallback model. This is useful for:

- Cloud model rate limits or outages.
- Graceful degradation when API keys expire.
- Cost optimization (use a cheap local model as fallback for expensive cloud models).

Fallback can be configured at:

- **`defaults.llm.fallback_model`** — Applies to all agents and the supervisor.
- **Per-agent `llm.fallback_model`** — Overrides the default for a specific agent.
- **`supervisor.fallback_model`** — Overrides the default for the supervisor specifically.

## Temperature Control

The `temperature` parameter controls randomness in LLM responses:

- **`0.0`** — Fully deterministic (always picks the most likely token).
- **`0.1–0.3`** — Best for factual/tool-calling agents (consistency preferred).
- **`0.7–0.9`** — Best for creative tasks (variety preferred).
- **`1.0`** — Maximum randomness.

Default: `0.2` (favors consistency).

## LLM Usage Patterns in Orchid

### Simple Completions (Summarization, Routing)

Use `self.summarise()` which calls `self._chat_model.ainvoke()`. A `BaseChatModel` must be injected via `chat_model=` — there is no fallback.

```python
response = await self.summarise(
    query,
    rag_data=rag_context,
    conversation_history=history,
)
```

### Agentic Tool-Calling Loops

When you need `tool_calls` from the response (agentic loops), use `litellm` directly with a lazy import inside the method:

```python
async def run(self, state):
    import litellm  # Lazy import — only needed for tool-calling
    response = await litellm.acompletion(
        model="openai/gpt-4o",
        messages=messages,
        tools=tools,
    )
```

Add a comment explaining why `litellm` is used directly (tool-calling inherently depends on the OpenAI function-calling protocol).

### Never Import litellm at Module Level

Consumer agents must not import `litellm` at module level for simple summarization. Use `self.summarise()` or `self._llm_service` instead.

## API Key Configuration

API keys are configured in `orchid.yml` or via environment variables:

```yaml
llm:
  model: openai/gpt-4o
  openai_api_key: ${OPENAI_API_KEY}
  anthropic_api_key: ${ANTHROPIC_API_KEY}
  gemini_api_key: ${GEMINI_API_KEY}
  groq_api_key: ${GROQ_API_KEY}
```

Environment variables take priority over YAML values. Use `${VAR_NAME}` syntax in YAML to reference environment variables.

## Ollama Configuration

For local Ollama models, specify the API base URL:

```yaml
llm:
  model: ollama/llama3.2
  ollama_api_base: http://host.docker.internal:11434
```

In Docker, use `http://host.docker.internal:11434` to reach the host's Ollama instance. In local development, `http://localhost:11434` works.
