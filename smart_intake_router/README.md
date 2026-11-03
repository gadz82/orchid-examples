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
Synthesis still needs a chat model; the default is `ollama/llama3.2`.

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

## Use Jev (or another decision model) for routing

The example ships with the stub so it runs offline. To let a real decision model choose the
agent, replace the `router` provider and point `decisions.routing` at it:

```yaml
allowed_decision_hosts: [api.example.com]

decision_models:
  jev:
    protocol: state-questions          # TypeSafe's System One dialect; `systemone` is an alias
    model: jev-latest
    base_url: https://api.example.com
    decide_path: /v1/systemone         # provider-specific path; defaults to /v1/decide
    api_key_env: DECISION_API_KEY
    timeout_seconds: 2.0

decisions:
  routing:
    model: jev
    confidence_threshold: 0.8
    on_low_confidence: llm             # llm (default), default, or escalate
  # Keep the other points on the stub while you validate routing:
  skills:
    model: router
  tools:
    model: router
  rag:
    model: router
```

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

`state-questions` covers the state-and-questions dialect; `openai-compatible` covers the
OpenAI Decisions shape. The transport validates egress, bounds the call, and falls back to the
supervisor's LLM routing on any failure.

## Tests

```bash
cd workspace-py
.venv/bin/python -m pytest examples/smart_intake_router/tests -x --no-cov
```

The tests exercise the real config, the real stub provider, routing, skill selection, the tool
shortlist, and the HTTP surface (API e2e with a deterministic chat model).
