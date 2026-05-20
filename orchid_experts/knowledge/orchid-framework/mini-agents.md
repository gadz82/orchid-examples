<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/mini-agents.mdx, and codebase analysis -->

# Mini-Agents

Mini-agents are an opt-in feature that allows a single agent to fan out a complex query into multiple parallel sub-tasks, each handled by a focused "mini-agent" with a curated tool subset. This is useful for complex queries that benefit from specialized, parallel processing within a single agent's domain.

## How Mini-Agents Work

### Overview

When mini-agents are enabled on an agent, the following flow occurs:

1. **Decomposition** — A deterministic structured-output decomposer analyzes the user query at the start of the agent's turn.
2. **Fork** — If the decomposer returns `should_fork=True`, the graph fans out into N parallel mini-agent nodes.
3. **Execution** — Each mini-agent runs a focused agentic loop with a curated tool subset.
4. **Aggregation** — Results from all mini-agents are synthesized back into one `AIMessage` by the aggregator.

### Configuration

Mini-agents are enabled via YAML on a top-level agent:

```yaml
agents:
  research-agent:
    description: "Research agent with mini-agent support"
    prompt: "You are a research specialist..."
    mini_agent:
      enabled: true
```

### No Nesting

Mini-agents cannot be nested. The `mini_agent.enabled: true` flag only works on top-level agents. A mini-agent cannot itself spawn sub-mini-agents.

## Decomposition

The decomposer is a structured-output LLM call that analyzes the user query and decides whether to fork:

```python
class DecomposerOutput(BaseModel):
    should_fork: bool
    sub_tasks: list[SubTask]

class SubTask(BaseModel):
    id: str
    instruction: str
    tool_subset: list[str]
```

### Decomposition Criteria

The decomposer decides to fork when:

- The query contains multiple distinct sub-questions that can be answered independently.
- Different sub-questions require different tool subsets.
- Parallel processing would be faster than sequential tool calls.

### Limits

- **Default cap:** 3 mini-agents per turn.
- **Hard cap:** 8 mini-agents per turn.

The decomposer cannot create more than 8 sub-tasks, regardless of query complexity.

## Execution

Each mini-agent node runs a focused agentic loop:

1. Receives its specific instruction from the decomposer.
2. Has access only to its curated tool subset (not all tools available to the parent agent).
3. Runs the standard agent pipeline (RAG, tools, LLM) within its scope.
4. Returns its result as a structured output.

### Tool Subset Curation

The decomposer assigns each sub-task a `tool_subset` — a list of tool names relevant to that sub-task. This:

- Reduces token usage (fewer tool descriptions in the prompt).
- Improves tool selection accuracy (the LLM sees only relevant tools).
- Prevents tool conflicts (different mini-agents don't compete for the same tools).

## Aggregation

The aggregator synthesizes all mini-agent outcomes back into one `AIMessage`:

1. Collects results from all mini-agent nodes.
2. Calls the LLM with a synthesis prompt that combines the original query and all mini-agent results.
3. Returns a single `AIMessage` to the user.

The aggregation prompt is configurable and can be customized to control the synthesis format.

## Shadow-Slot Keys

Cross-node data uses shadow-slot keys in the graph state:

- **`mini_agent_outcomes[f"{parent}#{mini_id}"]`** — Stores the outcome of each mini-agent.
- **`mini_agent_decisions[parent_name]`** — Stores the decomposer's decisions for the parent agent.

These keys are namespaced to avoid conflicts between different parent agents and different turns.

## SSE Events

Four lifecycle SSE events surface mini-agent activity to the streaming UI:

| Event | Description |
|-------|-------------|
| `mini_agent.decomposed` | The decomposer has split the query into sub-tasks. |
| `mini_agent.started` | A mini-agent has started execution. |
| `mini_agent.finished` | A mini-agent has completed its task. |
| `mini_agent.aggregated` | The aggregator has synthesized all results. |

These events provide visibility into the mini-agent lifecycle without leaking inner token streams.

## Graph Integration

The decomposer hook lives at the **graph-wrapper** level (`graph._create_agent_node`), not inside `GenericAgent.run()`. This means:

- Any `OrchidAgent` subclass can opt in via YAML without coordinating with its own `run()` method.
- The graph wrapper handles the fork/aggregate logic transparently.
- The agent's `run()` method is unaware of mini-agent decomposition.

## When to Use Mini-Agents

Mini-agents are appropriate when:

- A single query naturally decomposes into independent sub-questions.
- Each sub-question benefits from a focused tool subset.
- Parallel processing would reduce overall latency.

They are NOT appropriate when:

- Sub-questions depend on each other's results (use cross-agent skills instead).
- The query is simple enough for a single tool call.
- The agent doesn't have enough tools to benefit from subset curation.

## Example

```yaml
agents:
  analyst:
    description: "Data analyst with mini-agent support"
    prompt: "You are a data analyst..."
    tools: [query_db, generate_chart, summarize_data, compare_metrics]
    mini_agent:
      enabled: true
```

When a user asks: *"Compare Q3 revenue and user growth, and generate charts for both"*:

1. The decomposer splits this into:
   - Sub-task 1: "Query Q3 revenue data" → tools: `[query_db, summarize_data]`
   - Sub-task 2: "Query Q3 user growth data" → tools: `[query_db, summarize_data]`
   - Sub-task 3: "Generate comparison charts" → tools: `[generate_chart]`
2. Three mini-agents run in parallel.
3. The aggregator combines the results into a single response with charts and analysis.
