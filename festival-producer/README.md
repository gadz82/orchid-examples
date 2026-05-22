# Festival Producer — Multi-Agent + rag_augmented Demo

Three GenericAgents (artist booking, logistics, marketing) with cross-agent orchestrator
skills, backed by **rag_augmented** conversation memory — Orchid's most advanced
summarization pipeline.

## What It Demonstrates

| Feature | How It's Used |
|---|---|
| **Multi-agent routing** | Supervisor routes to `artist-booking`, `logistics`, or `marketing` based on question type |
| **Orchestrator skills** | `full_production_review` runs all 3 agents sequentially; `budget_optimization` and `stage_planning` run 2 agents each |
| **rag_augmented memory** | Past turns embedded in Qdrant; queries retrieve the 5 most semantically relevant exchanges |
| **Structured JSON entities** | Artists, venues, budgets tracked as typed entities; deduplicated across turns |
| **Middle truncation** | Long rider specs and stage configs truncated preserving start+end |
| **Per-agent prompt overrides** | Each agent has custom `summary_compression_*` prompts in its `prompt_sections` |
| **SQLite persistence** | Summaries survive restarts via `conversation_summaries` table |

## Agents

| Agent | Tools | Expertise |
|---|---|---|
| `artist-booking` | `lookup_artist`, `list_available_artists`, `get_rider_details`, `compare_artists` | Artist availability, fee negotiation, lineup curation |
| `logistics` | `check_venue_availability`, `get_schedule_overview`, `estimate_power_budget`, `get_crew_requirements` | Stage specs, power grids, scheduling, crew |
| `marketing` | `analyze_demographics`, `get_pricing_strategy`, `recommend_channels`, `project_attendance` | Demographics, ticket pricing, channel mix |

## Orchestrator Skills

```yaml
skills:
  full_production_review:     # booking → logistics → marketing
  budget_optimization:        # booking → marketing
  stage_planning:             # booking → logistics
```

Each skill is invoked by the supervisor when it detects a matching intent.

## Memory Config

```yaml
supervisor:
  memory:
    strategy: "rag_augmented"
    summary_recent_turns: 12
    structured_output: true
    persist_summary: true
    rag_k: 5
    rag_similarity_threshold: 0.5
    store_turns: true
    truncation_strategy: "middle"
    truncation_max_chars: 1000
```

## Usage

```bash
ORCHID_CONFIG=examples/festival-producer/orchid.yml uvicorn orchid_api.main:app
# or via CLI:
orchid chat interactive --config examples/festival-producer/orchid.yml
```

## Example Conversations

```
User: I need a headliner for Saturday night. Budget is $100K.
→ Supervisor routes to artist-booking
→ lookup_artist + list_available_artists return candidates
→ Agent recommends Solar Eclipse Collective ($120K) or Neon Cathedral ($60K)

User: Can the Main Stage handle Solar Eclipse Collective's power requirements?
→ Supervisor routes to logistics
→ get_rider_details confirms 32A three-phase
→ check_venue_availability confirms Main Stage has 400A grid

User: What's our projected revenue if we go with Neon Cathedral as Saturday headliner?
→ Supervisor invokes budget_optimization skill
→ compare_artists (booking) + project_attendance (marketing)
→ Agents collaborate: booking provides draw data, marketing projects revenue

User: Give me a full production review for the current lineup.
→ Supervisor invokes full_production_review skill
→ booking → logistics → marketing in sequence
→ Each agent sees prior agent's output via mcp_context
→ Running summary extended incrementally across all 3 agent turns
→ RAG retrieves past discussions about each artist from previous sessions
```

## Related

- [Gallery Curator](/examples/gallery-curator) — Single-agent summarization demo
- [Chat Summarization concept](/concepts/chat-summarization)
- [Supervisor concept](/concepts/supervisor)
