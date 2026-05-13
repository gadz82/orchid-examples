# GraphRAG knowledge-base example

Single-agent demo showing the `graph_rag` retrieval strategy
(ADR-026) backed by Orchid's `InMemoryGraphStore`. The startup hook
seeds a tiny org-chart corpus + companion vector chunks so the agent
can answer multi-hop questions like:

- "Who reports to Alice?"
- "Which projects does Bob's team work on?"
- "Who is two hops up the chain from Dave?"

## What's interesting

1. **`graph_rag` retrieval.** Each query first hits the graph store
   to find seed entities (string match against entity names), then
   walks `max_hops: 2` of the configured `relation_filter:
   [reports_to, works_on, manages]`. The serialised sub-graph is
   fused with vector hits when `fuse_with_vectors: true`.

2. **In-memory graph store wired via the startup hook.** The hook
   builds an `InMemoryGraphStore`, seeds entities + edges, and
   assigns it to `runtime.graph_store`. The graph builder picks it
   up at agent construction time and threads it into
   `_step_rag_retrieval`.

3. **Per-scope isolation.** The seed uses `tenant_id: "__shared__"`
   so the graph is visible to every authenticated tenant. Real
   integrators would scope per-tenant so each customer's org-chart
   stays isolated.

## Running it

```bash
ORCHID_CONFIG=examples/graph_kb/orchid.yml \
  uvicorn orchid_api.main:app --port 8000
```

Or via CLI:

```bash
orchid chat send "Who reports to Alice?" \
  --agent org_chart \
  --config examples/graph_kb/orchid.yml

orchid chat send "Which projects does Dave work on?" \
  --agent org_chart \
  --config examples/graph_kb/orchid.yml
```

## File layout

```
examples/graph_kb/
├── README.md          (this file)
├── agents.yaml        (single org_chart agent + graph_rag config)
├── orchid.yml         (runtime config + startup hook wiring)
└── hooks/
    └── startup.py     (seeds InMemoryGraphStore + vector chunks)
```

## Production notes

For a production deployment, swap the in-memory graph store for
`Neo4jGraphStore`:

```yaml
# orchid.yml
rag:
  graph_store_backend: neo4j
  neo4j_url: bolt://neo4j:7687
  neo4j_user: neo4j
  neo4j_password: ${NEO4J_PASSWORD}
```

…and replace this example's startup hook with one that seeds the
graph from your authoritative source (org-chart API, project DB,
…). The agent's YAML stays unchanged — `graph_rag` retrieval works
the same way regardless of which `OrchidGraphStore` implementation
is wired.
