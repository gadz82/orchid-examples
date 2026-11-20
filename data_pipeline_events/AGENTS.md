# Event-Driven Data Pipeline Example — Agent Guide

Self-contained Pollen/Bloom example built on the direct `data_pipeline` DAG.

## Layout

- `agents.yaml` — pipeline DAG, events store/queue, HTTP ingestion source, two triggers and one schedule.
- `orchid.yml` — API bootstrap: local identity resolver, SQLite chat storage, null vector backend, local-sink startup hook.
- `identity.py` — permissive resolver used by the webhook (`act_as_user`) and scheduler (`service_account`) paths.
- `steps.py` — deterministic operators (copied; examples do not import each other).
- `tests/` — hermetic harness with SQLite event storage, in-memory chat, fake model and a fake scheduler backend.

## Rules

- Keep tests hermetic: `FakeChatModelFactory`, no Ollama, no network, temp SQLite only.
- The webhook trigger must keep `respect_chat_binding: true` and `act_as_user`; the scheduler uses `service_account`.
- Never put a bearer token in a signal, a pipeline output or a chat message.
- Synthetic data only.
- The pipeline chains one predecessor per job; do not add multi-predecessor convergence (v1 scheduling limitation).

## Test

```bash
cd workspace-py
../.venv/bin/python -m pytest examples/data_pipeline_events -m "not integration" --import-mode=importlib -x
```
