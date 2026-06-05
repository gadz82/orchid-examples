<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/supervisor.mdx, and codebase analysis -->

# Supervisor

The supervisor is the central routing brain of the Orchid multi-agent system. It is a LangGraph node that decides which agent(s) should handle each user query, orchestrates parallel or sequential agent execution, manages cross-agent skills, and synthesizes multi-agent responses into a single coherent answer.

## Core Responsibilities

### Routing

The routing step analyzes the user's message and decides which agent(s) should handle it:

1. Reads each agent's `description` field from the configuration.
2. Uses the LLM to match the query against available agent descriptions.
3. Selects one or more agents based on relevance.
4. Considers `execution_hints.parallel_safe` to decide whether to run agents in parallel or sequentially.

The routing prompt is configurable via `supervisor.routing_system_prompt`. When `null`, the built-in template from `supervisor.py` is used.

### Synthesis

After all selected agents return their results, the supervisor synthesizes them into a single coherent response:

1. Collects all agent responses (from parallel or sequential execution).
2. Calls the LLM with a synthesis prompt that combines the original query and all agent results.
3. Returns a single `AIMessage` to the user.

The synthesis prompt is configurable via `supervisor.synthesis_system_prompt`.

### Sequential Advance (Skills)

During orchestrator skill execution, after each step completes, the supervisor decides whether to advance to the next step or respond directly. This is controlled by `supervisor.sequential_advance_prompt`.

## Configuration

```yaml
supervisor:
  assistant_name: "My Assistant"
  routing_system_prompt: |
    Custom routing prompt...
  synthesis_system_prompt: |
    Custom synthesis prompt...
  sequential_advance_prompt: |
    Custom sequential advance prompt...
  history_max_turns: 20
  history_max_chars: 1000
  history_summary_enabled: true
  history_summary_model: "ollama/llama3.2"
  history_summary_recent_turns: 10
```

### assistant_name

The name used in the supervisor's prompts when referring to itself. Appears in synthesized responses. Set this to your product's name.

### routing_system_prompt

Fully custom system prompt for the supervisor's routing step. Override to change how agents are selected (e.g., to add domain-specific routing rules or prioritization logic).

### synthesis_system_prompt

Custom system prompt for the synthesis step. Override to control the tone, format, or structure of final responses.

### sequential_advance_prompt

Custom prompt used during orchestrator skill execution. After each step in a multi-agent skill completes, this prompt decides whether to advance to the next step or respond directly.

### history_max_turns

Maximum number of user-assistant conversation pairs included as context in supervisor routing, synthesis, and sequential advance steps. Each "turn" is one user message + one assistant response. Default: `20`.

### history_max_chars

Maximum characters per individual message in conversation history. Messages exceeding this limit are truncated with an ellipsis. Default: `1000`.

### history_summary_enabled

Enables sliding-window conversation summarization. When `true`, conversation turns older than `history_summary_recent_turns` are compressed into a single LLM-generated summary paragraph, while the most recent turns are kept verbatim. Default: `true`.

### history_summary_model

LLM model used for the history summarization call. Use a cheap/fast model here since the summarization input is small. When `null`, the supervisor's default model is used.

### history_summary_recent_turns

Number of recent user-assistant exchange pairs to keep verbatim when summarization is enabled. Default: `10`.

## Parallel vs. Sequential Execution

The supervisor uses `execution_hints.parallel_safe` to decide execution mode:

- **`parallel_safe: true`** (default) — The supervisor may run this agent concurrently with other agents for a single query.
- **`parallel_safe: false`** — The supervisor runs this agent sequentially. Set when the agent depends on results from other agents, has side effects, or when tool execution order matters.

## Cross-Agent Skills

When the supervisor detects that a user query matches a skill's `description`, it activates the skill instead of normal routing:

1. The skill's steps are executed sequentially.
2. Each step invokes one agent with a specific instruction.
3. Results from each step are passed forward as context to the next step.
4. After all steps complete, the supervisor synthesizes the final response.

Skills are defined at the root level of `agents.yaml`:

```yaml
skills:
  my-skill:
    description: "When to activate this skill"
    steps:
      - agent: agent-a
        instruction: "First step instruction"
      - agent: agent-b
        instruction: "Second step instruction, using results from agent-a"
```

## Graph Integration

The supervisor is built into the LangGraph by `build_graph()`:

```python
from orchid_ai import load_config, OrchidRuntime
from orchid_ai.graph.graph import build_graph  # low-level factory; the Orchid facade calls it for you

config = load_config("agents.yaml")
runtime = OrchidRuntime(default_model="ollama/llama3.2")
graph = build_graph(config=config, runtime=runtime)
```

The graph structure is:

```
START → supervisor_routing → [parallel/sequential agents] → supervisor_synthesis → END
```

For skills, the graph adds intermediate nodes for each skill step.
