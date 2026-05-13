# RAG-strategies showcase

Four agents share a small dated knowledge base (release notes seeded
by the startup hook) but each picks a different
`OrchidRetrievalStrategy`. Compare results from the same query to
build intuition for which strategy fits which workload.

## Files

```
examples/rag-strategies/
├── README.md
├── __init__.py
├── orchid.yml                     # startup.hook + LLM + storage
├── agents.yaml                    # 4 agents, one per strategy
├── hooks/
│   ├── __init__.py
│   └── startup.py                 # registers recency_simple + seeds corpus
└── strategies/
    ├── __init__.py
    └── recency.py                 # custom OrchidRetrievalStrategy
```

## Strategy comparison

| Agent | Strategy | Latency | Recall | When to use |
|---|---|---|---|---|
| `simple_searcher` | `simple` | Fastest (1 query) | Baseline | Short, well-formed questions; near-verbatim matches |
| `multi_query_searcher` | `multi_query` | 1 + N paraphrases | High | Users phrase the same intent many ways |
| `hyde_searcher` | `hyde` | 1 + N hypotheticals | High for off-distribution queries | Vocabulary mismatch between user and corpus |
| `recency_searcher` | `recency_simple` (custom) | Same as simple | Baseline + time-bias | Time-sensitive corpus (release notes, news) |

`multi_query` and `hyde` both fan out — they trade extra LLM round
trips for broader candidate sets. Pair them with `query_transformers:
[reformulate]` (already on every agent here) and the conversation-
aware rewrite happens once at agent entry, before the strategy fans
out.

## The custom `recency_simple` strategy

`strategies/recency.py` subclasses `OrchidRetrievalStrategy` and:

1. Oversamples the dense retrieval (pulls `2 * k` candidates).
2. Re-ranks by a configurable metadata field — defaults to
   `published_at` — descending.
3. Returns the top `k` after re-rank.

It honours the ABC's `from_config` hook so YAML knobs flow in:

```python
@classmethod
def from_config(cls, config):
    recency_field = getattr(config, "recency_field", "published_at")
    recency_weight = getattr(config, "recency_weight", 1.0)
    return cls(recency_field=recency_field, recency_weight=recency_weight)
```

`recency_weight` blends recency into the semantic score:

- `0.0` → tie-break only (semantic order preserved unless scores match)
- `1.0` → recency dominates (default in this example)
- `0.5` → 50/50 blend

## Where strategies plug in

The `OrchidRetrievalStrategy` ABC lives in `core/retrieval.py`. The
runtime path is:

1. Agent calls `get_retrieval_strategy(name, config)` per turn.
2. Registry looks the name up; missing → falls back to `"simple"`.
3. Strategy's `from_config(config)` constructs an instance.
4. Strategy's `retrieve(...)` returns the ranked `OrchidSearchResult` list.

Registration happens once at process startup. The hook in
`hooks/startup.py` calls `register_retrieval_strategy("recency_simple",
RecencySimpleRetrieval)` before any agent is invoked, so the registry
is warm.

## Running

```bash
# Validate the YAML loads
orchid config validate examples/rag-strategies/agents.yaml

# Run the API (with Qdrant for the embedding store)
ORCHID_CONFIG=examples/rag-strategies/orchid.yml \
  uvicorn orchid_api.main:app --port 8000

# Ask the same question through each agent and compare:
for agent in simple_searcher multi_query_searcher hyde_searcher recency_searcher; do
  echo "=== $agent ==="
  curl -s -X POST http://localhost:8000/messages \
    -H 'Content-Type: application/json' \
    -d "{\"agent\": \"$agent\", \"query\": \"what changed about MCP auth?\"}"
  echo
done
```

Try queries like:

- "what changed about MCP auth?" — `hyde` and `multi_query` shine on
  vague phrasing.
- "release 5.4" — `simple` matches the literal release ID instantly.
- "latest changes" — `recency_searcher` surfaces the newest note even
  if older notes score higher semantically.

## Adapting

To register your own retrieval strategy:

1. Subclass `OrchidRetrievalStrategy` (in `orchid_ai.core.retrieval`).
2. Implement `async def retrieve(...)` matching the ABC signature.
3. Optionally override `from_config(cls, config)` to pull YAML knobs.
4. Register it from a startup hook:
   ```python
   from orchid_ai.rag.strategies import register_retrieval_strategy
   register_retrieval_strategy("my_strategy", MyStrategy)
   ```
5. Reference it from YAML: `agents.<name>.rag.retrieval.strategy: my_strategy`.

## Built-in strategies you can study

- `orchid_ai.rag.strategies.simple.SimpleRetrieval` — single dense call
- `orchid_ai.rag.strategies.multi_query.MultiQueryRetrieval` — paraphrase fan-out
- `orchid_ai.rag.strategies.hyde.HyDERetrieval` — hypothetical-document
- `orchid_ai.rag.strategies.hybrid.HybridRetrieval` — dense + sparse fusion (BM25 / SPLADE)
- `orchid_ai.rag.strategies.graph_rag.GraphRAGRetrieval` — knowledge-graph augmented retrieval

Each one is a single file under `orchid_ai/rag/strategies/` — short,
readable, and a good template for your own.
