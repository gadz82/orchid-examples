# FM Agent — AI Development Context

This file is the source of truth for AI agents working on the **FM Agent** Orchid example. It complements `README.md` with implementation details, constraints, and conventions specific to this package.

## Project identity

- **Name:** `orchid-example-fm-agent`
- **Purpose:** Personal AI assistant fleet for a platform engineering team.
- **Runtime:** Orchid (LangGraph + FastAPI), PostgreSQL, Qdrant, optional Neo4j.
- **Language:** Python 3.11+, with TypeScript/Next.js frontend in a separate root package.

## Scope

`workspace-py/examples/fm_agent/` is a **consumer project** in the Orchid monorepo. It is *not* a core `orchid*` package, so platform-specific terms (e.g., Docebo) are permitted here when they describe real integrations. Framework-level code must still live in `orchid/`.

## Architecture overview

| Layer | Key files | Responsibility |
|---|---|---|
| Config | `config/orchid.yml` | Runtime config: LLM, RAG, storage, startup hook |
| Config | `config/agents/_shared.yaml` | Defaults, supervisor, guardrails, skills, events/triggers, MCP gateway overrides |
| Config | `config/agents/<agent>.yaml` | One dedicated file per agent (definition, RAG namespace, per-agent MCP servers) |
| Startup | `hooks/startup.py` | Registers custom strategies/guardrails, runs MCP allowlist diff |
| RAG strategies | `recency_strategy.py` | `recency_hybrid` retrieval strategy |
| Guardrails | `secret_guardrail.py` | Secret-detection output guardrail |
| Live capture | `hooks/capture.py`, `hooks/mcp_guard.py` | Normalize/store tool results, fail-open allowlist checks |
| Bloom jobs | `bloom_jobs.py`, `bloom_dispatcher.py` | Event-driven job handlers for the 9 triggers in `agents.yaml` |
| Indexer | `indexer/`, `indexer_router.py` | CLI and REST API for docs/cards/graph/kb/prune/raw ingestion |
| Evals | `evals/` | Draft generation, code validation, eval harness |
| Tests | `tests/` | Unit tests + one optional Docker integration test |

## Agent fleet

All agents except `cartographer`, `sre-investigator`, and `delivery-analyst` reuse the `_shared_persona` YAML anchor.

| Agent | Namespace | Notes |
|---|---|---|
| `notification-expert` | `svc-notification` | Service expert |
| `mailer-expert` | `svc-mailer` | Service expert |
| `push-expert` | `svc-push` | Service expert |
| `eventbus-expert` | `svc-eventbus` | Service expert |
| `domains-expert` | `svc-domains` | Service expert |
| `devops-expert` | `svc-devops` | Service expert |
| `messenger-expert` | `svc-messenger` | Service expert |
| `standards-coach` | `eng-standards` | Coding standards |
| `cartographer` | `platform-graph` | Graph RAG, custom prompt |
| `sre-investigator` | `runbooks` | Datadog + Confluence + GitLab MCP, custom prompt |
| `delivery-analyst` | `tickets` | Jira + GitLab + Confluence MCP, custom prompt |

Static service experts and `standards-coach` set `rag.retrieval.exclude_dynamic: true` so their RAG namespace is not polluted with dynamic captures.

## MCP servers

- `atlassian-rovo` — declared once in `config/agents/_shared.yaml` under `defaults.mcp_servers`, so it is available to **every** agent. OAuth, read-only allowlist for Confluence/Jira.
- `gitlab` — passthrough, read tools + wildcard for sre/delivery analysts; declared per-agent where needed.
- `datadog` — passthrough, read-only logs/metrics; declared only on `sre-investigator`.
- `slack` — passthrough, `chat_postMessage` / `chat_postEphemeral`; declared on `sre-investigator` and `delivery-analyst`.

`hooks/mcp_guard.py` diffs the configured Atlassian allowlist against advertised tools at startup. It is **fail-open**; connection failures are logged, not raised.

## Bloom (event-driven jobs)

`bloom_dispatcher.dispatch(trigger_id, ctx, payload)` routes to one of nine handlers in `bloom_jobs.py`. Every handler:

1. Computes a stable `dedupe_key`.
2. Short-circuits if a successful `JobRun` with that key already exists.
3. Writes a `JobRun` row with status `success`, `failed`, or `skipped`.

`JobRunStore` is pluggable: `InMemoryJobRunStore` for tests, `PostgresJobRunStore` for production.

## Indexer passes

CLI entry point: `fm-indexer` (`examples.fm_agent.indexer.cli:main`).

| Subcommand | Purpose |
|---|---|
| `docs` | Ingest READMEs, configs, specs |
| `cards` | Generate LLM module-summary cards |
| `graph` | Extract dependency graph into Neo4j |
| `kb` | Crawl whitelisted Help Center sections |
| `prune` | Remove vectors for deleted files |
| `raw` | One-off raw text ingestion |

REST equivalent: `POST /indexer/run` (requires `ALLOW_INDEX_ENDPOINT=true`).

### Upstream CLI parity (Prompt G — complete)

The framework-level `orchid index` command can now ingest the raw Markdown exports under `.knowledge/prompts/fm-agents/raw-input/` with:

- YAML front-matter parsing (`--front-matter`, `--id-field page_id`)
- Idempotent re-runs via a content-hash manifest (`--manifest`, `--prune`, `--force`)
- SQLite manifest by default, PostgreSQL via `--manifest-dsn`

Examples:

```bash
# Ingest Confluence exports into the runbooks namespace
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/confluence \
  -n runbooks \
  --front-matter \
  --id-field page_id \
  -c workspace-py/examples/fm_agent/config/orchid.yml

# Ingest KB articles into a product-kb namespace
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/kb \
  -n product-kb \
  --front-matter \
  --id-field article_id \
  -c workspace-py/examples/fm_agent/config/orchid.yml

# Re-run: unchanged files are skipped; removed files are pruned
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/confluence \
  -n runbooks \
  --front-matter \
  --id-field page_id \
  --prune \
  -c workspace-py/examples/fm_agent/config/orchid.yml

# Use a Postgres manifest backend
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/confluence \
  -n runbooks \
  --front-matter \
  --id-field page_id \
  --manifest-dsn postgresql://user:pass@localhost/orchid \
  -c workspace-py/examples/fm_agent/config/orchid.yml
```

See `.knowledge/prompts/fm-agents/features/prompt-g.md` for the implementation plan.

## Running the demo

Two equivalent ways to start the full stack:

```bash
# 1. From the example directory (uses its own docker-compose.yml)
cd workspace-py/examples/fm_agent
cp .env.example .env   # fill in GEMINI_API_KEY
docker compose up --build

# 2. From the workspace-py root (uses the shared dev compose)
cd workspace-py
make demo-fm_agent
```

The shared dev compose (`script/docker-compose.examples.yml`) activates the
`graph` profile automatically, so Neo4j starts alongside Qdrant, PostgreSQL,
and the Orchid MCP gateway. To skip Neo4j, use the example's own compose with
`--profile default`.

## Conventions

- **Python:** snake_case, `from __future__ import annotations`, target Python 3.11, line length 120.
- **Imports:** stdlib → third-party → `orchid_ai.*` → local `.` imports.
- **Async file I/O:** use `asyncio.to_thread(...)` with a sync helper; do not call blocking `open()` directly in async functions.
- **Exceptions:** catch specific exception types. Use `# noqa: BLE001` only for genuine fail-open boundaries (e.g., MCP list_tools at startup, LLM calls that may raise vendor-specific errors).
- **No Docebo in `orchid*` packages:** this rule does not apply here, but never move platform-specific code into `orchid/`.
- **Environment:** all secrets live in `.env` (gitignored). Never commit credentials.

## Testing

```bash
# Unit tests only (no Docker)
cd workspace-py/examples/fm_agent
PYTHONPATH=workspace-py pytest tests/ -m "not integration"

# Integration test (requires Docker)
pytest tests/test_integration.py -m integration

# Lint
ruff check .
```

Current status: **110 unit tests pass**, **full ruff clean**.

## Common pitfalls

1. **Do not edit `orchid/` framework code from this example.** If a framework change is needed, modify `workspace-py/orchid/` and verify `orchid-api/` / `orchid-cli/` still work.
2. **Directory config:** agent configuration lives in `config/agents/`. The loader merges every `*.yaml` / `*.yml` file in that directory; defining the same agent name in two files raises an error.
3. **Shared MCP servers:** `atlassian-rovo` is declared in `config/agents/_shared.yaml` under `defaults.mcp_servers`. To make another MCP server available fleet-wide, add it there rather than duplicating it in every agent file.
4. **MCP auth modes:** keep `datadog` and `slack` as `passthrough`; `atlassian-rovo` remains `oauth`.
5. **Slack tools:** only `chat_postMessage` and `chat_postEphemeral` are configured; do not add destructive tools.
6. **BOM/encoding:** raw ingestion handles UTF-8 with BOM and whitespace front-matter.
7. **RAG scoping:** always use `OrchidRAGScope`; never pass raw tenant filters.
8. **Do not commit `.env`.**

## Planned work

Implementation prompts live in `.knowledge/prompts/fm-agents/features/` and are the source of truth for upcoming phases.
