# examples/ — Agent Guide

Self-contained Orchid example projects. Each directory has its own
`orchid.yml`/`agents.yaml`, optional Python package, Docker files and tests.
The shared `_e2e_shared/` harness provides the in-process API builder, fake
model/vector/MCP fixtures and assertions. `script/start_*.sh` in
`workspace-py/` launches the shared demo stacks.

## Data pipeline examples

- `data_pipeline/` — direct typed DAG: deterministic, LLM, agent, decision, map,
  sub-pipeline and emit jobs. Docs: website `/concepts/pipelines` and
  `orchid/docs/pipelines.md`.
- `data_pipeline_events/` — the same pipeline started by a webhook and a cron
  schedule, with SQLite event storage, `act_as_user` identity and chat-bound
  results. Docs: website `/concepts/pipelines` and
  `orchid/docs/pipelines-extension.md`.

Both suites are hermetic (fake model, temp SQLite events, in-memory chat, no
network). Run them from `workspace-py`:

```bash
../.venv/bin/python -m pytest examples/data_pipeline examples/data_pipeline_events \
  -m "not integration" --import-mode=importlib -x
```

The pipeline examples chain one predecessor per job; v1 `depends_on` is a
scheduling edge, not an all-predecessor barrier.

## Test

```bash
cd workspace-py && make test-e2e-examples
```
