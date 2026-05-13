# Travel Agency — Orchid example

A multi-agent travel planner demonstrating most Orchid enhancements in a single cohesive domain.

## What it shows

| Feature | Where |
|---|---|
| Multi-agent sequential pipeline | `flights` → `hotels` → `itinerary` → `bookings` |
| **Custom OrchidAgent subclass** | `agents/itinerary.py` — reads sibling agent results from state |
| **HITL tool approval** | `book_flight`, `book_hotel`, `cancel_booking` — `requires_approval: true` |
| **LangGraph checkpointer** | `checkpointer: {type: sqlite}` — required by HITL |
| **Multi-query retriever** | `defaults.rag.retrieval.strategy: multi_query` + on `itinerary` agent |
| **Grounding guardrails** | On `flights` and `hotels` agents (anti-hallucination) |
| **Orchestrator skills** | `plan_trip` (search + itinerary), `book_my_trip` (flight+hotel booking) |
| **Startup hook** | `hooks/startup.py` seeds destination RAG + registers custom `estimate_trip_budget` tool |
| **Global guardrails** | Prompt injection block, max length, PII redaction |
| **LLM fallback + retry** | `fallback_model: ollama/llama3.2`, `retry_attempts: 2` |
| **Response caching** | `defaults.cache_enabled: true` |
| **Conversation compression** | `history_summary_enabled: true` |

## Package layout

```
examples/travel-agency/
├── README.md
├── __init__.py
├── config/
│   ├── agents.yaml          # agent definitions, tools, skills, guardrails
│   └── orchid.yml           # runtime: LLM, storage, checkpointer, startup hook
├── agents/
│   └── itinerary.py         # custom OrchidAgent subclass
├── tools/
│   ├── flights.py           # search_flights, get_flight_details
│   ├── hotels.py            # search_hotels, get_hotel_details
│   └── bookings.py          # book_flight, book_hotel, cancel_booking (HITL)
└── hooks/
    └── startup.py           # seeds destination RAG + registers custom tool
```

## Running

### Via orchid-api (recommended)

```bash
export GEMINI_API_KEY=your-key
ORCHID_CONFIG=examples/travel-agency/config/orchid.yml \
    uvicorn orchid_api.main:app --port 8000
```

### Via orchid-cli

```bash
export GEMINI_API_KEY=your-key
orchid chat interactive --config examples/travel-agency/config/orchid.yml
```

### Required services

- **Qdrant** running at `qdrant:6333` (or override `QDRANT_URL`) — destination guide RAG
- **Gemini API key** (or swap `llm.model` to `ollama/llama3.2` for local-only)

## Example prompts to try

1. **Flight search (simple)**:
   > "I need a flight from JFK to London, economy, under $800."

2. **Hotel search (filtered)**:
   > "Find me a 4-star hotel in Paris under $300/night with a bar."

3. **Full trip plan** (triggers the `plan_trip` skill → flights + hotels + itinerary):
   > "Plan me a 5-day London trip leaving from JFK on May 10. Budget-friendly, interested in museums."

4. **HITL booking** (triggers tool approval interrupt):
   > "Book flight AA101 for John Doe."
   
   The graph pauses and the API returns:
   ```json
   {
     "status": "interrupted",
     "approvals_needed": [{
       "tool": "book_flight",
       "args": {"flight_no": "AA101", "passenger_name": "John Doe"},
       "interrupt_id": "..."
     }]
   }
   ```
   Resume with:
   ```bash
   POST /chats/{chat_id}/resume
   {"approved": true}
   ```

5. **Custom budget tool (registered by startup hook)**:
   > "Estimate the budget for 5 nights at $210/night with $720 flights."

## Observability

Attach `OrchidMetricsHandler` to any graph invocation to collect per-request metrics:

```python
from orchid_ai import OrchidMetricsHandler

handler = OrchidMetricsHandler()
result = await graph.ainvoke(
    state,
    config={
        "configurable": {"thread_id": chat_id},
        "callbacks": [handler],
    },
)
print(handler.get_metrics())
# {
#   "total_tokens": 3420,
#   "llm_calls": 6,
#   "tool_calls": 4,
#   "retries": 0,
#   "avg_llm_latency_s": 0.91,
#   "agent_latencies_s": {"flights": 1.2, "hotels": 1.1, "itinerary": 2.3},
# }
```

## Extending this example

- **Add a new city**: edit `_HOTELS` in `tools/hotels.py` and `_DESTINATIONS` in `hooks/startup.py`
- **Add a new agent**: define it in `agents.yaml` — for config-only agents, no Python needed
- **Add custom MCP servers**: add an `mcp_servers:` list under any agent in `agents.yaml`
- **Swap checkpointer to PostgreSQL**: change `checkpointer.type` to `postgres` and install `langgraph-checkpoint-postgres`
- **Disable HITL for demos**: remove `requires_approval: true` from booking tools (but checkpointer still enables conversation-state persistence)
