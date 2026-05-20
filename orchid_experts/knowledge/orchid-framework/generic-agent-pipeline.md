<!-- Source: derived from orchid/AGENTS.md, orchid/README.md, orchid-website/src/content/concepts/agents.mdx, and codebase analysis -->

# GenericAgent Pipeline

The `GenericAgent` is the concrete, YAML-driven agent implementation in Orchid. It handles the standard 6-step flow entirely from configuration — no custom Python code needed. Most deployments never need to subclass it.

## The 6-Step Pipeline

When `GenericAgent.run()` is invoked, it executes these steps sequentially:

### Step 1: RAG Retrieval

If RAG is enabled (`rag.enabled: true`) and a reader is available, the agent:

1. Extracts the user query from graph state via `extract_user_query(state)`.
2. Builds an `OrchidRAGScope` from the auth context and state.
3. Calls `fetch_rag_context(query, scope)` to retrieve the top `k` documents from the vector store.
4. Stores retrieved documents in state for later use.

If RAG is disabled or the reader is `None`, this step is skipped.

### Step 2: Skill Detection

The agent checks if any agent-level skills match the user query:

1. The `SkillDetector` collaborator uses an LLM to match the query against available skill descriptions.
2. If a match is found, the `SkillExecutor` runs the skill's sequential steps.
3. Each step is either a tool call or an agent invocation, executed in order with accumulated results passed forward.
4. The skill result becomes the agent's response, bypassing remaining steps.

If no skill matches, the pipeline continues to step 3.

### Step 3: MCP Tool Calls

If the agent has MCP servers configured:

1. The `MCPDispatcher` discovers available tools from each server (using cached capabilities if warmed).
2. The LLM decides which tools to call based on the query and available tool descriptions.
3. Tools are called according to the configured `tool_call_strategy`:
   - **`all`** — Call every matched tool simultaneously.
   - **`sequential`** — Call tools one by one, passing accumulated results forward.
   - **`llm_decides`** — Ask the LLM to decide which tools to call and with what arguments.
4. Results are collected and stored in state.

If no MCP servers are configured or no tools match, this step is skipped.

### Step 4: Built-in Tool Calls

If the agent has built-in tools configured:

1. The LLM decides which built-in tools to call based on the query.
2. Tools are called in-process (no network overhead).
3. If a tool has `inject_to_rag: true`, its result is stored in the vector store for future retrieval.
4. Results are collected and stored in state.

If no built-in tools are configured, this step is skipped.

### Step 5: Dynamic RAG Injection

If any tool results were marked for RAG injection:

1. The agent retrieves previously injected tool results from the vector store that are within the TTL window.
2. These cached results are merged with the RAG context from step 1.
3. This allows the agent to reuse expensive tool results without re-calling the tool.

If no tools have `inject_to_rag: true`, this step is skipped.

### Step 6: LLM Summarization

The final step synthesizes all context into a response:

1. The agent calls `summarise(query, rag_data, conversation_history, prior_tool_context)`.
2. The injected `BaseChatModel` receives a prompt combining:
   - The agent's system prompt (from `prompt:` in YAML).
   - Retrieved RAG documents.
   - Tool call results (MCP + built-in).
   - Conversation history (extracted and truncated per supervisor limits).
3. The LLM generates a response, which is returned as an `AIMessage`.

## Configuration

The `GenericAgent` is configured entirely through `agents.yaml`:

```yaml
agents:
  my-agent:
    description: "Short description for supervisor routing"
    prompt: |
      System prompt sent to the LLM.
    rag:
      namespace: my-namespace
      k: 5
    tools: [my-tool, another-tool]
    mcp_servers:
      - name: my-server
        url: http://localhost:3001/mcp
        tools: "*"
    guardrails:
      input:
        - type: topic_restriction
          fail_action: warn
          config:
            allowed_topics: [topic1, topic2]
    execution_hints:
      parallel_safe: true
```

No `class:` field is needed — `GenericAgent` is the default.

## Custom Agent Subclassing

When YAML alone isn't enough, subclass `OrchidAgent` in a consumer project:

```python
from orchid_ai.core.agent import OrchidAgent
from orchid_ai.core.state import OrchidAgentState

class CustomAgent(OrchidAgent):
    async def run(self, state: OrchidAgentState) -> dict:
        # Custom logic here
        ...
```

Reference it via dotted import path:

```yaml
agents:
  custom:
    class: myproject.agents.custom.CustomAgent
    description: "Custom agent with special logic"
```

The framework resolves the class at startup via `importlib`. The agent inherits `summarise()`, `fetch_rag_context()`, `extract_user_query()`, and `extract_conversation_history()` from the base class.

## Mini-Agent Support

Mini-agents are opt-in via `mini_agent.enabled: true` on a top-level agent. When enabled:

1. A deterministic structured-output decomposer runs at the start of the agent's turn.
2. If it returns `should_fork=True`, the graph fans out into N parallel mini-agent nodes (default cap 3, hard cap 8).
3. Each mini-agent runs a focused agentic loop with a curated tool subset.
4. Results are synthesized back into one `AIMessage` via the aggregator.

The decomposer hook lives at the graph-wrapper level (`graph._create_agent_node`), not inside `GenericAgent.run()`. Cross-node data uses shadow-slot keys: `mini_agent_outcomes[f"{parent}#{mini_id}"]`, `mini_agent_decisions[parent_name]`.

Four lifecycle SSE events (`mini_agent.{decomposed,started,finished,aggregated}`) surface activity to the streaming UI.
