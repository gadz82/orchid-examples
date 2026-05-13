# Prompt customization showcase

This example demonstrates **every prompt-customization extension point**
Orchid exposes through configuration. It is intentionally small — a
single fictional `legal_advisor` agent — so the comparison with the
built-in defaults stays focused on the prompts themselves.

## What gets overridden

| Field | What it controls |
|---|---|
| `supervisor.assistant_name` | Brand name interpolated into supervisor prompts |
| `supervisor.routing_system_prompt` | System prompt for the routing-decision LLM call |
| `supervisor.synthesis_system_prompt` | System prompt for the response-synthesis LLM call |
| `agents.<name>.prompt` | The agent's primary system prompt (existing field) |
| `agents.<name>.prompt_sections.prior_results_header` | Header above the JSON dump of prior-turn tool results |
| `agents.<name>.prompt_sections.mcp_prompt_template` | Template for each rendered MCP prompt |
| `agents.<name>.prompt_sections.skipped_prompt_template` | Template for MCP prompts that need arguments |
| `agents.<name>.prompt_sections.resources_header` | Header above the MCP resources block |
| `agents.<name>.prompt_sections.resource_template` | Template for one MCP resource |
| `agents.<name>.prompt_sections.rag_header` | Header above the RAG context block |
| `agents.<name>.prompt_sections.prior_results_max_chars` | Truncation cap for the prior-results JSON dump |
| `agents.<name>.prompt_sections.resource_max_chars` | Per-resource truncation cap |
| `agents.<name>.prompt_sections.summarise_history_reminder` | Reminder block appended to the summarise system prompt when history is present |
| `agents.<name>.prompt_sections.summarise_prior_results_header` | Header above prior tool results inside the summarise system prompt |
| `agents.<name>.prompt_sections.summarise_rag_section_header` | Header above the RAG block inside the summarise USER message |
| `agents.<name>.prompt_sections.summarise_user_template` | Template for the summarise USER message (placeholders: `{query}`, `{rag_section}`, `{mcp_data}`) |
| `agents.<name>.prompt_sections.summarise_prior_results_max_chars` | Truncation cap for the prior-results JSON dump in summarise |
| `agents.<name>.rag.retrieval.transformer_prompts.multi_query` | Multi-query transformer system prompt |
| `agents.<name>.rag.retrieval.transformer_prompts.hyde.single` | HyDE single-paragraph generator prompt |
| `agents.<name>.rag.retrieval.transformer_prompts.hyde.multi` | HyDE multi-paragraph generator prompt |
| `agents.<name>.rag.retrieval.transformer_prompts.decompose` | Query-decomposition transformer prompt |
| `agents.<name>.rag.retrieval.transformer_prompts.reformulate` | Conversation-aware reformulation prompt |
| `agents.<name>.mini_agent.system_prompt_template` | Per-sub-task system prompt for mini-agent forks |
| `agents.<name>.mini_agent.decomposer_prompt` | Decomposer's structured-output system prompt |
| `agents.<name>.mini_agent.aggregator_prompt` | Aggregator's synthesis prompt |

## Inheritance

Defaults flow from the top-level `defaults.rag.retrieval.transformer_prompts`
block to every agent. Per-agent overrides under
`agents.<name>.rag.retrieval.transformer_prompts` take precedence; any
field left unset inherits from defaults. The `agents.yaml` in this
directory shows the layering — `defaults` sets a custom `reformulate`
prompt, and the agent overrides `multi_query`, `hyde.{single,multi}`,
and `decompose` while inheriting the default `reformulate`.

## Placeholder contracts

When supplying a custom template you MUST keep the placeholders the
default uses, otherwise `str.format` will raise at runtime:

- `mcp_prompt_template` → `{name}`, `{text}`
- `skipped_prompt_template` → `{name}`, `{description}`, `{required_args}`
- `resource_template` → `{name}`, `{content}`
- `transformer_prompts.multi_query` → `{n}`
- `transformer_prompts.hyde.multi` → `{n}`
- `transformer_prompts.decompose` → `{n}`
- `mini_agent.system_prompt_template` → `{parent_prompt}`, `{instruction}`, `{tool_list}`
- `mini_agent.decomposer_prompt` → `{agent_name}`, `{agent_description}`,
  `{agent_prompt}`, `{tool_inventory}`, `{user_query}`, `{history}`,
  `{history_max_turns}`, `{max_count}`
- `prompt_sections.summarise_user_template` → `{query}`, `{rag_section}`, `{mcp_data}`

The `prior_results_header`, `resources_header`, and `rag_header`
templates have no placeholders — they're plain strings.

## Programmatic equivalent (embedded Python)

Every YAML field has a Python counterpart on the matching Pydantic
model. Embedded users can build the same configuration imperatively:

```python
from orchid_ai.config.schema import (
    OrchidAgentConfig,
    OrchidAgentPromptConfig,
    OrchidQueryTransformerPromptsConfig,
    OrchidRAGConfig,
    OrchidRetrievalConfig,
)

prompts = OrchidQueryTransformerPromptsConfig(
    multi_query="Generate {n} legal phrasings...",
    decompose="Split into {n} legal sub-issues...",
)
prompts.hyde.single = "Write a single legal-treatise paragraph..."

config = OrchidAgentConfig(
    description="Legal advisor",
    prompt="You are an expert legal research assistant.",
    prompt_sections=OrchidAgentPromptConfig(
        rag_header="\n=== SOURCE CITATIONS ===",
        resource_max_chars=4000,
    ),
    rag=OrchidRAGConfig(
        namespace="legal",
        retrieval=OrchidRetrievalConfig(
            strategy="hyde",
            query_transformers=["reformulate"],
            transformer_prompts=prompts,
        ),
    ),
)
```

## Running

```bash
# Validate the YAML loads with the new fields
orchid config validate examples/prompt-customization/agents.yaml

# Run the API
ORCHID_CONFIG=examples/prompt-customization/orchid.yml \
  uvicorn orchid_api.main:app --port 8000
```

This example reuses the basketball example's SQLite chat-storage
backend (see `orchid.yml`), so no extra infrastructure is required
beyond Ollama + Qdrant — same as the other demos.
