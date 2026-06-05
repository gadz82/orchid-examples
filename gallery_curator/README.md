# Gallery Curator — Conversation Summarization Demo

An AI assistant for art gallery curators that remembers artists, exhibitions, sales results, and
visitor feedback **across sessions** using Orchid's layered conversation memory system.

**Why this example exists:** The Gallery Curator is a purpose-built demonstration of every
feature in the [conversation summarization](/concepts/chat-summarization) improvement pipeline
(Phases 1–5). It is also a genuinely useful multi-session assistant — the kind of tool a small
gallery team would run daily.

## What It Demonstrates

| Feature | Phase | How It's Used |
|---|---|---|
| **Incremental running summary** | 1 | The curator agent extends its summary with each new exhibition discussion instead of re-summarizing from scratch (O(n) instead of O(n²)). |
| **Structured JSON entity extraction** | 2 | Artists (`"Ruth Asawa"`, `"Olafur Eliasson"`), venues, and sales figures are tracked as typed entities. The LLM produces structured JSON; on parse failure it falls back to narrative. |
| **RAG-augmented semantic retrieval** | 3 | When a curator asks *"what did we discuss about the Venice Biennale?"*, Orchid embeds the query and retrieves the most semantically relevant past turns from Qdrant under the `__memory__` namespace. |
| **Configurable compression prompts** | 4 | The gallery agent overrides the default `summary_compression_system_prompt` and `summary_extension_user_prompt` with gallery-specific instructions. |
| **Smart truncation** (`middle`) | 4 | Long auction result listings are truncated with the `middle` strategy — the first 40% (which item?) and last 40% (how much?) are preserved with a `…[truncated]…` marker in between. |
| **Unified message filtering pipeline** | 5 | Internal `[Supervisor]` routing messages, `[Conversation summary]` artifacts, and tool-call noise are removed by a single `MessageFilterPipeline` preset shared by supervisor, synthesizer, and agent. |
| **SQLite persistence** | 1–3 | Summaries survive process restarts via the `conversation_summaries` table. |
| **Per-agent prompt customization** | 4 | `prompt_sections` block overrides compression prompts without subclassing. |

## Memory Config Deep-Dive

The full `supervisor.memory` block in `agents.yaml`:

```yaml
supervisor:
  history_summary_enabled: true
  history_summary_model: gemini/gemini-2.5-flash-lite
  history_max_turns: 30
  history_max_chars: 1200

  memory:
    strategy: "rag_augmented"          # Phase 1 + 3: incremental summary + Qdrant retrieval
    summary_recent_turns: 8            # keep last 8 exchanges verbatim
    summary_model: gemini/gemini-2.5-flash-lite
    structured_output: true            # Phase 2: JSON with entities
    persist_summary: true              # store in conversation_summaries table
    structured_output: true
    # -- RAG (Phase 3) --
    rag_k: 5
    rag_similarity_threshold: 0.5
    store_turns: true
    # -- Truncation (Phase 4) --
    truncation_strategy: "middle"
    truncation_max_chars: 800
```

**Graceful degradation:** If Qdrant is unavailable (`NullVectorReader`), `get_relevant_history()` returns `[]` and the system silently degrades to `running_summary`-only — no crash, no user-facing error.

## Files

```
examples/gallery_curator/
├── README.md              # This file
├── orchid.yml             # Infrastructure: SQLite, Qdrant, Ollama
└── agents.yaml            # Gallery curator agent + supervisor config + memory
```

No custom Python agent classes — everything is `GenericAgent` driven by YAML.

## Structured Entity Example

When `structured_output: true`, after a few turns the LLM might produce:

```json
{
  "topics": ["upcoming exhibition", "Venice Biennale", "artist availability"],
  "entities": [
    {"name": "Ruth Asawa", "type": "person", "details": "sculptor; available Q3; $15k estimated per piece"},
    {"name": "Venice Biennale", "type": "product", "details": "group show April 2027; booth confirmed"},
    {"name": "Matsue Gallery", "type": "other", "details": "potential co-exhibitor; pending contract"}
  ],
  "actions_taken": ["confirmed booth application", "requested artist catalogues"],
  "decisions": ["delay Olafur Eliasson piece to Q1 2028"],
  "open_questions": ["shipping insurance for bronze sculptures?"],
  "user_preferences": ["prefers post-war abstract over contemporary installation"],
  "narrative": "Curator is planning a Venice Biennale group show with Ruth Asawa sculptures. Contacted Matsue Gallery for co-exhibition. Deferred the Eliasson installation.",
  "covered_turns": 12
}
```

The rendered `to_context_string()` injected into the LLM:

```
Topics: upcoming exhibition, Venice Biennale, artist availability
Entities:
  - Ruth Asawa (person): sculptor; available Q3; $15k estimated per piece
  - Venice Biennale (product): group show April 2027; booth confirmed
  - Matsue Gallery (other): potential co-exhibitor; pending contract
Actions taken: confirmed booth application; requested artist catalogues
Decisions: delay Olafur Eliasson piece to Q1 2028
Open questions: shipping insurance for bronze sculptures?
User preferences: prefers post-war abstract over contemporary installation
Summary: Curator is planning a Venice Biennale group show...
```

## Usage

### Prerequisites

- Ollama running with `llama3.2`, `nomic-embed-text`, `minicpm-v`
- Qdrant for `rag_augmented` strategy (optional — degrades gracefully without it)
- Python 3.11+ with `orchid-ai`, `orchid-cli` installed

### Start the API

```bash
ORCHID_CONFIG=examples/gallery_curator/orchid.yml uvicorn orchid_api.main:app --port 8000
```

### CLI (no API needed)

```bash
orchid chat interactive --config examples/gallery_curator/orchid.yml
```

### Docker Compose

```bash
docker compose -f docker-compose.demo.yml up --build
```

## Conversation Flow

Here's a simulated multi-turn session showing how the memory evolves:

**Turn 1:**
> User: *I'm planning the spring exhibition. Who are our confirmed artists?*

Agent looks up the catalog (built-in tool). No prior context yet.

**Turn 5:**
> User: *What was the budget for Ruth Asawa's shipping?*

At this point the running summary covers turns 1–4. The query about "budget" triggers RAG retrieval of semantically similar past turns about finances.

**Turn 15:**
> User: *Remind me of all the decisions we made about Venice.*

The running summary has been incrementally extended 10+ times (no O(n²) re-summarization). The structured JSON now tracks 8+ entities. RAG retrieves the 5 most relevant past turns about "Venice" from Qdrant. The LLM receives: [RAG turns about Venice] + [incremental summary] + [last 8 verbatim exchanges].

The result is accurate, contextual, and cheap — the LLM only processes the delta, not the entire 15-turn history.

## Related Docs

- [Chat Summarization concept page](/concepts/chat-summarization)
- [Configuration Atlas — supervisor.memory](/configuration)
- [Supervisor concept](/concepts/supervisor)
- [RAG concept](/concepts/rag)
- [Prompt Customization example](/examples/prompt-customization)
