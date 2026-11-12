# Smart intake router — decision models in action

A four-agent SaaS support desk for the fictional **Northwind Cloud**. One decision provider
handles all four decision points:

| Decision point | What the provider decides |
|---|---|
| Routing | which agent(s) handle the request, and parallel vs sequential |
| Skills | whether an orchestrator workflow (`refund_request`) applies |
| Tools | whether the billing agent may see `lookup_invoice` |
| RAG | which retrieved passages survive into context (the example disables RAG, so the gate has no passages to filter) |

The default profile is a deterministic **stub**, so the example runs with no key and no network.
Synthesis still needs a chat model; the default is `ollama/gemma4:26b`.

## Try it

```bash
# from the workspace root
ORCHID_CONFIG=workspace-py/examples/smart_intake_router/config/orchid.yml \
  orchid chat interactive
```

Sample messages and the decisions they produce:

- `I was charged twice for the same invoice` → billing, tool shortlist includes `lookup_invoice`
- `Please refund the duplicate charge` → the `refund_request` orchestrator skill
- `The dashboard is down for everyone` → technical

## Run the full stack (Docker)

```bash
cd workspace-py/examples/smart_intake_router
cp .env.example .env
docker compose up --build
# API: http://localhost:8080/health
# UI:  http://localhost:3000
```

The compose stack starts the API and the frontend (the shared `orchid-frontend` image,
cloned from GitHub; the first build can take a few minutes), and uses the Ollama daemon
installed on the host at `host.docker.internal:11434`; no model is downloaded into a
container. Pull the model on the host first:

```bash
ollama pull gemma4:26b
```

The decisions use the stub by default and need no key. On CPU-only hosts, Ollama is slow for
interactive synthesis; set `LLM_MODEL` to a hosted provider (and its key) in `.env` for fast
replies, or use a GPU. The deterministic chat coverage lives in `tests/test_api_e2e.py`,
which injects a `FakeChatModel` and does not need Ollama.

From the workspace root: `make demo-smart_intake_router` (runs
`workspace-py/script/start_smart_intake_router.sh`) or `make run-smart_intake_router`
(direct compose; both are auto-discovered).

This runner uses the example's own compose (SQLite + Ollama) rather than the shared
`script/run_example.sh` compose, which assumes PostgreSQL and Gemini. The divergence is
intentional (ADR-001).

To inspect the exact command without starting Docker:

```bash
bash workspace-py/script/start_smart_intake_router.sh --dry-run
```

## Use TypeSafe/Jev for routing

The example ships with the stub so it runs offline. The `jev` provider is declared in
`config/agents.yaml` but is inactive by default. Enable it with two environment variables:

```bash
export TYPESAFE_API_KEY=...        # from your TypeSafe account
export DECISION_ROUTING_MODEL=jev
```

The provider block is:

```yaml
allowed_decision_hosts: [api.typesafe.ai]

decision_models:
  jev:
    protocol: state-questions          # TypeSafe's System One dialect; `systemone` is an alias
    model: jev-latest
    base_url: "${TYPESAFE_BASE_URL:-https://api.typesafe.ai}"
    decide_path: /v1/systemone
    api_key_env: TYPESAFE_API_KEY
    timeout_seconds: 2.0

decisions:
  routing:
    model: "${DECISION_ROUTING_MODEL:-router}"
    confidence_threshold: 0.8
    on_low_confidence: llm             # llm (default), default, or escalate
    history_max_turns: 10              # default; max conversation turns sent to Jev
    history_max_chars: 400             # per-message truncation
  # Keep the other points on the stub while you validate routing:
  skills:
    model: router
  tools:
    model: router
  rag:
    model: router
```

`TYPESAFE_BASE_URL` defaults to `https://api.typesafe.ai`; set it only for a gateway, and add
that gateway's hostname to `allowed_decision_hosts`. The other decision points stay on the
stub, so the example remains offline and key-free unless you opt in.

On every turn Jev is asked:

- one boolean per candidate agent, named `agent:<name>`, with the agent description in the
  question instructions;
- one `execution` choice (`parallel` or `sequential`);
- one `skill` choice when orchestrator skills exist, so a confident skill match can bypass agent
  routing.

The supervisor selects every agent whose boolean clears `confidence_threshold` and dispatches.
Synthesis still uses the chat model — the decision model only routes. Low confidence, a
missing/refused answer, a timeout, or a provider error falls back to the existing LLM supervisor
(with `escalate`, or a deterministic rephrase request with `default`). `sequential` with more than one
selected agent also falls back to the LLM, because independent booleans cannot express dependency
order.

The provider sees the latest user query plus a filtered excerpt of up to three recent turns; tool
output and supervisor messages are excluded.

Through a gateway, keep `protocol: state-questions` and point `base_url`/`decide_path` at the
gateway endpoint (for example `/v1/evaluate`). For the OpenAI Decisions shape use
`protocol: openai-compatible` with `decide_path: /v1/decisions`. For a plain chat model use
`protocol: llm` with the model string; it is the slowest option but requires no decision provider.

### RAG flavours

The RAG gate runs after the selected retrieval strategy returns, so it applies to `simple`,
`hybrid`, `hyde`, `multi_query`, and `graph_rag`. For `graph_rag`, the strategy first selects graph
nodes with the decision model and then serialises the surviving sub-graph; the final passages still
pass through the chunk gate.

Use `decisions.rag.strategies` to restrict the gate (omit it to apply to every strategy):

```yaml
decisions:
  rag:
    model: jev
    confidence_threshold: 0.8
    strategies: [simple, hybrid, graph_rag]
```

The decision state includes each passage's text, score, and source, so the provider can weigh
provenance as well as content. HyDE and multi-query still generate their variants; the gate filters
what reaches synthesis, not how the variants are produced.

`state-questions` covers the state-and-questions dialect; `openai-compatible` covers the
OpenAI Decisions shape. The transport validates egress, bounds the call, and falls back to the
supervisor's LLM routing on any failure.

## Enable another decision point

The four keys above are the legacy points. The nine newer points are enabled
additively under `decisions.points`, without changing the legacy keys or any
default:

```yaml
decisions:
  points:
    retrieval_strategy:
      model: router                      # an existing decision_models entry
      confidence_threshold: 0.8
      options:
        strategies: [simple, hyde]       # candidate allowlist
```

`retrieval_strategy` picks the RAG strategy per query before retrieval; the
legacy `rag` gate still filters the passages afterwards. The other registered
points are `model_routing`, `tool_choice`, `guardrails`, `memory`, `events`,
`ingestion`, `delegation`, and `agentic_loop`.

Only the points you list run. Everything else keeps its current behaviour, and a
low-confidence, refused, timed-out, failed, or unknown answer falls back to the
behaviour already configured (the agent's retrieval strategy, its chat model,
the deterministic processors, no delegation, and so on).

Agent-scoped points can be overridden under
`agents.<name>.decisions.points.<point>`, or opted out with `enabled: false`
there: `retrieval_strategy`, `model_routing`, `tool_choice`, `guardrails`,
`ingestion`, `delegation`, and `agentic_loop`. `memory` and `events` are
fleet-scoped, so they are configured globally only; a per-agent block for them
is rejected.

The stub does not have to answer the new question: with no answer it defaults to
the first offered candidate option at the stub's configured `confidence` (0.9 by
default). Add an explicit `strategy` choice to make the selection deterministic:

```yaml
decision_models:
  router:
    protocol: stub
    stub:
      answers:
        strategy:
          choice: simple
          confidence: 0.95
```

`DECISION_ROUTING_MODEL=jev` changes only the example's legacy `routing` point;
it does not change the new point's `model`. `retrieval_strategy` keeps
`model: router` unless you point it at `jev` explicitly.

See `orchid_ai/decision/AGENTS.md` for the registration, config validation,
binding, fallback, and observability contract.

## Tests

```bash
cd workspace-py
make test-e2e-examples FLAGS='-k smart_intake'
```

The tests exercise the real config, the real stub provider, routing, skill selection, the tool
shortlist, and the HTTP surface (API e2e with a deterministic chat model).
