# Data Pipeline Example — Agent Guide

Self-contained direct data-pipeline example for the Orchid framework.

## Layout

- `agents.yaml` — shapes, relations, decision provider, events and both pipeline definitions.
- `orchid.yml` — API bootstrap: agents path, SQLite storage (container DSN), null vector backend, local-sink startup hook.
- `steps.py` — deterministic operator functions (`load_account`, `usage_item`, `propose`, `snapshot`).
- `hooks/startup.py` — attaches a process-local signal emitter for direct CLI runs.
- `tests/` — direct facade, HTTP, CLI and runner-contract e2e coverage.

## Rules

- Tests must stay hermetic: use `examples._e2e_shared.fixtures.mock_llm.FakeChatModelFactory`; never call Ollama or a provider.
- The pipeline uses one explicit predecessor per job. Do not introduce multi-predecessor convergence; see the v1 scheduling note in `workspace-py/orchid/docs/pipelines.md`.
- Keep the emitted envelope identity-only: never add the bearer token to an emit payload.
- Synthetic data only.

## Test

```bash
cd workspace-py
../.venv/bin/python -m pytest examples/data_pipeline -m "not integration" --import-mode=importlib -x
```

The runner contract test skips in a standalone examples checkout because it needs
the sibling `script/` and `Makefile`.

## Docs

- Website: https://orchestratorindex.com/concepts/pipelines
- Framework: `workspace-py/orchid/docs/pipelines.md`
- Extensions: `workspace-py/orchid/docs/pipelines-extension.md`
