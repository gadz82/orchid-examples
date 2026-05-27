# Architecture Review Board — Multi-Agent + rag_augmented Demo

Three GenericAgents forming a virtual design review board: structural engineering,
cost estimation, and sustainability consulting. Cross-agent orchestrator skills run
sequential pipelines (design → cost → sustainability) with each agent seeing prior
output via `mcp_context`. Backed by **rag_augmented** memory.

## What It Demonstrates

| Feature | How It's Used |
|---|---|
| **Multi-agent routing** | Supervisor routes to `structural`, `cost`, or `sustainability` based on question type |
| **Orchestrator skills** | `full_design_review` runs all 3 sequentially; `material_selection` runs structural + sustainability |
| **rag_augmented memory** | Past design decisions and material comparisons retrieved from Qdrant on each new query |
| **Structured JSON entities** | Materials, jurisdictions, certifications tracked as typed entities with deduplication |
| **Middle truncation** | Long code compliance lists and carbon calculations preserved start+end |
| **Per-agent prompt overrides** | Each agent has domain-specific `summary_compression_*` prompts |
| **SQLite persistence** | Design review summaries survive restarts |

## Agents

| Agent | Tools | Expertise |
|---|---|---|
| `structural` | `analyze_structure`, `check_code_compliance`, `compare_materials`, `get_fire_strategy` | Load analysis, material selection, Eurocode/IBC/ASCE, fire safety |
| `cost` | `estimate_construction_cost`, `compare_lifecycle_costs`, `get_market_rates` | Construction budgets, lifecycle economics, regional rates |
| `sustainability` | `evaluate_certification`, `calculate_embodied_carbon`, `get_sustainability_strategies`, `compare_carbon_footprints` | BREEAM/LEED/DGNB, embodied carbon, green strategies |

## Orchestrator Skills

```yaml
skills:
  full_design_review:     # structural → cost → sustainability
  material_selection:     # structural → sustainability
```

## Memory Config

```yaml
supervisor:
  memory:
    strategy: "rag_augmented"
    structured_output: true
    rag_k: 6
    rag_similarity_threshold: 0.45
    truncation_strategy: "middle"
```

Lower `rag_similarity_threshold` (0.45 vs default 0.5) because design review discussions
often use different terminology for the same concept (e.g., "CLT" vs "cross-laminated timber"
vs "mass timber").

## Usage

```bash
ORCHID_CONFIG=examples/architecture_review/orchid.yml uvicorn orchid_api.main:app
orchid chat interactive --config examples/architecture_review/orchid.yml
```

## Example Conversations

```
User: Review a 6-story office building in Berlin, 8000m², targeting LEED Gold.
→ Supervisor invokes full_design_review skill
→ structural: steel frame + CLT slabs recommended, Eurocode 3 compliant
→ cost: €22.4M estimated, CLT lifecycle 30% cheaper than steel-concrete
→ sustainability: LEED Gold achievable, embodied carbon 40% below baseline

User: What if we switch to all-timber construction?
→ Supervisor routes to material_selection skill
→ structural: CLT + glulam viable to 12m spans, fire rating sufficient with encapsulation
→ sustainability: carbon negative (-210 kgCO2/m³ net), BREEAM Outstanding becomes possible
→ RAG retrieves past discussion about material costs from earlier sessions

User: Compare the carbon footprints of all three structural options we discussed.
→ Supervisor routes to sustainability
→ compare_carbon_footprints evaluates CLT vs steel vs concrete from past analyses
→ Running summary extended incrementally — only new comparison delta sent to LLM
→ Structured JSON tracks all 3 materials as entities with carbon data
```

## Related

- [Festival Producer](/examples/festival-producer) — Multi-agent rag_augmented demo (music industry)
- [Gallery Curator](/examples/gallery-curator) — Single-agent summarization demo
- [Chat Summarization concept](/concepts/chat-summarization)
