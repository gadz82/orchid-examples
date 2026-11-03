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

## Switch to a real decision model

Replace the `router` block in `config/agents.yaml` with an HTTP provider and add the host to
`allowed_decision_hosts`:

```yaml
allowed_decision_hosts: [api.example.com]
decision_models:
  router:
    protocol: state-questions        # or openai-compatible
    model: decision-model-v1
    base_url: https://api.example.com
    api_key_env: DECISION_API_KEY
```

`state-questions` covers the state-and-questions dialect; `openai-compatible` covers the
OpenAI Decisions shape. The transport validates egress, bounds the call, and falls back to the
supervisor's LLM routing on any failure.

## Tests

```bash
cd workspace-py
.venv/bin/python -m pytest examples/smart_intake_router/tests -x --no-cov
```

The tests exercise the real config, the real stub provider, routing, skill selection, and the
tool shortlist.
