# Data Pipeline Example — Typed Customer Health DAG

A direct data pipeline that turns synthetic account data into a typed
customer-health report. The pipeline is declared in YAML, runs through the
Orchid pipeline runner and uses every supported job kind: deterministic, LLM,
agent, decision, map, sub-pipeline and emit.

No frontend, no MCP gateway and no Qdrant. State is SQLite in the container and
in-memory in the direct tests. The decision provider is the deterministic
`stub`, so no provider key is needed; LLM and agent jobs use a local Ollama
model in the Docker profile. The e2e suite replaces the chat model with a
deterministic fake, so tests need neither Ollama nor a network.

## Run with Docker

From `workspace-py`, use the Makefile targets:

```bash
make demo-data_pipeline    # start via script/start_data_pipeline.sh
make run-data_pipeline     # docker compose up --build
```

Or run the example's own compose file directly:

```bash
cp .env.example .env
docker compose up --build
```

The API listens on `http://localhost:8080` in both paths.

The API is at `http://localhost:8080` and exposes `POST /pipelines/customer_health/runs`:

```bash
curl -sS -X POST http://localhost:8080/pipelines/customer_health/runs \
  -H 'Authorization: Bearer dev-token' \
  -H 'Content-Type: application/json' \
  -d '{"input": {"customer_id": "C-100"}, "include_graph": true}'
```

The example's events layer is in-memory; the `notify` job emits a
`pipeline.customer_health.completed` signal that the API dispatcher accepts.
A direct CLI run uses the startup hook's local sink instead.

## Run directly (Python)

```python
import asyncio
from orchid_ai import Orchid


async def main() -> None:
    orchid = await Orchid.from_config_path(
        "examples/data_pipeline/orchid.yml",
        apply_yaml=True,
        agents_config_path="examples/data_pipeline/agents.yaml",
        chat_storage_class="memory",  # or a host-writable SQLite DSN
    )
    try:
        result = await orchid.run_pipeline(
            "customer_health",
            {"customer_id": "C-100"},
            user_id="u-1",
            tenant_id="t-1",
            include_graph=True,
        )
        print(result.status, result.output)
    finally:
        await orchid.close()


asyncio.run(main())
```

This direct path needs Ollama for the LLM and agent jobs. Pass
`chat_storage_class="memory"` (shown above) or a writable
`chat_db_dsn` because the container DSN (`/data/data_pipeline.db`) is not
writable on a normal host.

The CLI uses the same configuration:

```bash
orchid pipeline list --config examples/data_pipeline/orchid.yml
orchid pipeline run customer_health \
  --config examples/data_pipeline/orchid.yml \
  --input-json '{"customer_id":"C-100"}' --output json
```

## Pipeline shape

```text
load_account ──► usage_map ──► assess ──► route ──► propose ──► escalate ──► report ──► notify
      │
      └────────► snapshot (sub-pipeline: account_snapshot)
```

| Job | Kind | What it does |
|-----|------|--------------|
| `load_account` | deterministic | Writes the synthetic `Account` object |
| `usage_map` | map | Fans out over `input.regions`, writes one `Usage` per region and links `has_usage` |
| `assess` | llm | Produces an `Assessment` shape from the account + usage graph |
| `route` | decision | Selects `retain`, `review` or `escalate` through the stub provider |
| `propose` | deterministic | Turns the label into an `Action` recommendation |
| `escalate` | agent | Runs the leaf `advisor` agent for a one-paragraph note |
| `snapshot` | subpipeline | Runs `account_snapshot` and returns its `Snapshot` output |
| `report` | llm | Produces the final `Report` shape |
| `notify` | emit | Emits the completion signal with the report headline |

The output is the typed `Report` (`headline`, `body`, `risk`). The result also
contains per-job statuses, graph statistics and the type counts
(`Account`, `Usage`, `Assessment`, `Action`, `Report`).

## Tests

```bash
cd workspace-py
../.venv/bin/python -m pytest examples/data_pipeline -m "not integration" --import-mode=importlib -x
```

The suite covers the direct facade, the HTTP API and the CLI with a
deterministic chat model — no API key, no Ollama and no network. The runner
contract test is Docker-free and checks `start_data_pipeline.sh` plus the
Makefile targets.

## Files

| File | Purpose |
|------|---------|
| `agents.yaml` | Shapes, relations, decision provider, events and both pipeline definitions |
| `orchid.yml` | API config: agents path, SQLite storage, null vector backend, startup hook |
| `steps.py` | Deterministic operator functions |
| `hooks/startup.py` | Local signal sink for direct runs without the events subsystem |
| `docker-compose.yml` | API + SQLite only (no frontend, no Qdrant, no MCP) |
| `tests/` | Direct, API, CLI and runner-contract e2e tests |

## Learn more

- [Data Pipelines guide](https://github.com/gadz82/orchid/blob/main/docs/pipelines.md) — YAML, shapes, job kinds, result contract, limits.
- [Pipeline extension guide](https://github.com/gadz82/orchid/blob/main/docs/pipelines-extension.md) — custom steps, class-based shapes, registered kinds and trust boundary.
- [Documentation site](https://orchestratorindex.com/concepts/pipelines) — the same concepts with the site navigation.
