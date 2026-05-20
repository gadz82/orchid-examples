<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/agents.mdx, and codebase analysis -->

# Skill Executor

The `SkillExecutor` is the collaborator responsible for executing multi-step skills within an agent. It works alongside the `SkillDetector` (which matches queries to skills) and the agent's main pipeline.

## Role in the Pipeline

The `SkillExecutor` runs during step 2 of the GenericAgent pipeline:

1. **Step 1: RAG Retrieval** — Retrieve relevant documents.
2. **Step 2: Skill Detection** — The `SkillDetector` checks if any skills match the query. If yes, the `SkillExecutor` runs the skill.
3. **Step 3: MCP Tool Calls** — (Skipped if a skill matched.)
4. **Step 4: Built-in Tool Calls** — (Skipped if a skill matched.)
5. **Step 5: Dynamic RAG Injection** — (Skipped if a skill matched.)
6. **Step 6: LLM Summarization** — Synthesize the skill result into a response.

When a skill matches, the `SkillExecutor` takes over and steps 3–5 are bypassed.

## Execution Flow

The `SkillExecutor` executes skill steps sequentially:

### Step 1: First Step

The first step is executed with the user's original query as context:

```python
result_1 = await self._execute_step(
    step=skill.steps[0],
    query=user_query,
    accumulated_results=[],
)
```

### Step 2: Subsequent Steps

Each subsequent step receives the accumulated results from all previous steps:

```python
result_2 = await self._execute_step(
    step=skill.steps[1],
    query=user_query,
    accumulated_results=[result_1],
)
```

### Final Result

After all steps complete, the accumulated results are returned:

```python
return {
    "messages": [AIMessage(content=format_results(all_results))],
}
```

## Step Execution

### Tool Steps

For tool steps, the `SkillExecutor`:

1. Resolves the tool from the registry (built-in or MCP).
2. Calls the tool with the query and accumulated results.
3. Returns the tool result.

```python
async def _execute_tool_step(step, query, accumulated_results):
    tool = resolve_tool(step.tool, source=step.source)
    result = await tool(
        query=query,
        context={"accumulated_results": accumulated_results},
        **step.arguments,
    )
    return result
```

### Agent Steps

For agent steps, the `SkillExecutor`:

1. Resolves the target agent from the agent registry.
2. Invokes the agent's `run()` method with the step instruction and accumulated results.
3. Returns the agent's response.

```python
async def _execute_agent_step(step, query, accumulated_results):
    agent = resolve_agent(step.agent)
    result = await agent.run(
        state={
            "messages": [{"role": "user", "content": step.instruction}],
            "accumulated_results": accumulated_results,
        },
    )
    return result
```

## Error Handling

The `SkillExecutor` handles errors at each step:

- If a step fails, the error is included in the accumulated results.
- The next step receives the error as context.
- The skill continues executing (unless the error is fatal).

This allows skills to handle partial failures gracefully.

## SkillDetector Collaboration

The `SkillDetector` and `SkillExecutor` work together:

1. **SkillDetector** — Matches the user query against available skill descriptions using an LLM. Returns the matching skill name (or `None`).
2. **SkillExecutor** — If a skill matched, executes the skill's steps sequentially.

The `SkillDetector` runs before the `SkillExecutor` in the pipeline. If no skill matches, the `SkillExecutor` is not invoked.

## Agent-Level vs. Orchestrator-Level Skills

### Agent-Level Skills

- Defined within an agent's `skills` section.
- Executed by the agent's `SkillExecutor`.
- Steps can be tool calls or agent invocations.
- The skill result becomes the agent's response.

### Orchestrator-Level Skills

- Defined at the root `skills` section of `agents.yaml`.
- Executed by the supervisor (not the `SkillExecutor`).
- Steps are always agent invocations.
- The supervisor runs each step sequentially, passing results forward.

The `SkillExecutor` only handles agent-level skills. Orchestrator-level skills are handled by the supervisor's sequential advance logic.

## Configuration

The `SkillExecutor` has no independent configuration. It uses the agent's configuration:

- **`skills`** — The skills available to the agent.
- **`tools`** — The built-in tools available to the agent.
- **`mcp_servers`** — The MCP servers available to the agent.

The `SkillExecutor` resolves tools and agents from these configurations at execution time.

## Best Practices

- **Keep skills short** — 2–4 steps is a good range. Longer skills are harder to debug.
- **Write clear step instructions** — Each step's instruction should be specific and actionable.
- **Test skills independently** — Skills should be testable without the full agent pipeline.
- **Handle errors gracefully** — Tools and agents invoked by skills should return meaningful error messages.
- **Don't nest skills** — A skill step cannot invoke another skill. This prevents infinite recursion.
