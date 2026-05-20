<!-- Source: derived from orchid-website/src/content/concepts/agents.mdx, orchid-website/src/content/concepts/tool-strategies.mdx, and codebase analysis -->

# Skill Definition

Skills are multi-step workflows that chain tool calls or agent invocations within or across agents. There are two types of skills in Orchid:

1. **Agent-level skills** — Internal to one agent, chaining tool calls or sub-agent invocations within the agent's domain.
2. **Orchestrator-level skills (cross-agent skills)** — Span multiple agents, executed by the supervisor.

## Agent-Level Skills

Agent-level skills are defined within an agent's configuration:

```yaml
agents:
  analyst:
    description: "Data analyst agent"
    prompt: "You are a data analyst..."
    skills:
      analyze-and-chart:
        description: "Analyze data and generate a chart"
        steps:
          - tool: query_db
            source: builtin
            arguments:
              max_results: 100
          - tool: generate_chart
            source: builtin
            arguments:
              chart_type: bar
```

### Step Types

Each step is either a tool call or an agent invocation (exactly one of `tool` or `agent` must be set):

#### Tool Step

```yaml
- tool: query_db
  source: builtin
  arguments:
    max_results: 100
```

- **`tool`** — Name of the tool to call (MCP tool name or built-in tool name).
- **`source`** — Where to find the tool. Set to an MCP server `name` (e.g., `"airline-api"`) for MCP tools, or `"builtin"` for built-in Python tools. Default: `"builtin"`.
- **`arguments`** — Extra arguments passed to the tool for this specific step. Merged with the tool's default arguments.

#### Agent Step

```yaml
- agent: data-collector
  instruction: "Collect data for the requested analysis"
```

- **`agent`** — Name of another agent to invoke directly (bypasses the supervisor).
- **`instruction`** — Query or instruction sent to the invoked agent. Overrides the user's original message for this step.

### Execution Flow

1. The `SkillDetector` matches the user query against available skill descriptions.
2. If a match is found, the `SkillExecutor` runs the skill's steps sequentially.
3. Each step receives the accumulated results from all previous steps.
4. The final result becomes the agent's response.

## Orchestrator-Level Skills (Cross-Agent)

Cross-agent skills are defined at the root level of `agents.yaml`:

```yaml
skills:
  plan-trip:
    description: "Plan a complete trip: find flights, book hotels, and suggest activities"
    steps:
      - agent: flights
        instruction: "Find flights from origin to destination for the given dates"
      - agent: hotels
        instruction: "Find hotels near the destination airport for the same dates"
      - agent: activities
        instruction: "Suggest activities at the destination based on the flight and hotel results"
```

### How They Work

1. The supervisor's LLM reads the skill's `description` to decide whether to activate it.
2. If activated, the supervisor runs each step sequentially.
3. Each step invokes one agent with a specific instruction.
4. Results from each step are passed forward as context to the next step.
5. After all steps complete, the supervisor synthesizes the final response.

### Step Configuration

```yaml
steps:
  - agent: agent-name
    instruction: "Specific instruction for this step"
```

- **`agent`** — Name of the agent to invoke (must match a key in the `agents` dict).
- **`instruction`** — Specific instruction or question passed to the agent for this step. This overrides the user's original query for this step.

## Skill Detection

The `SkillDetector` uses an LLM to match the user query against available skill descriptions:

```python
# The SkillDetector sends the query and skill descriptions to the LLM
# The LLM decides which skill (if any) matches the query
```

### Writing Good Descriptions

Skill descriptions should clearly state the end-to-end outcome:

- **Good:** "Plan a complete trip: find flights, book hotels, and suggest activities at the destination."
- **Bad:** "Trip planning skill."

The description should include:

- What the skill does.
- When to activate it.
- What agents/tools it uses.

## Skill Execution

The `SkillExecutor` runs the skill's steps:

1. **Step 1** — Executes the first step with the user's original query.
2. **Step 2** — Executes the second step with the accumulated results from step 1.
3. **...** — Continues for all steps.
4. **Final** — Returns the accumulated results.

### Accumulated Results

Each step receives the accumulated results from all previous steps as context:

```python
# Step 1 result
flights_result = "Found 3 flights..."

# Step 2 receives flights_result as context
hotels_result = "Found 5 hotels near the airport..."

# Step 3 receives both flights_result and hotels_result as context
activities_result = "Based on the flight and hotel results, here are activities..."
```

## When to Use Agent-Level Skills

- **Internal workflows** — When a sequence of tool calls is specific to one agent's domain.
- **Tool chaining** — When tool B depends on the output of tool A.
- **Sub-agent invocation** — When an agent needs to delegate a sub-task to another agent within its domain.

## When to Use Cross-Agent Skills

- **Multi-domain workflows** — When a task spans multiple agent domains.
- **Sequential agent chaining** — When the output of agent A is needed by agent B.
- **Complex user queries** — When a single query requires input from multiple agents in a specific order.

## Best Practices

- **Keep skills focused** — Each skill should accomplish one end-to-end outcome.
- **Write clear descriptions** — The LLM uses descriptions to decide when to activate skills.
- **Order steps logically** — Steps should flow from data gathering to analysis to output.
- **Test skills independently** — Skills should be testable without the full agent pipeline.
- **Don't overuse skills** — Skills add complexity. Use them only when the workflow justifies it.
