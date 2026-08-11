# FM Agent — Personal AI Assistant Fleet

A multi-agent Orchid deployment providing an AI-powered personal assistant for
software engineering work.  The fleet includes service-expert agents backed by RAG
over internal repos, cross-cutting agents for incident investigation, delivery
analysis, and coding standards, and an orchestrator-index for task routing.

Built on **Orchid** (LangGraph + FastAPI), with PostgreSQL for chat persistence,
Qdrant for vector RAG, and optional Neo4j for graph-based dependency queries.

## Quickstart

```bash
cp .env.example .env   # fill in GEMINI_API_KEY
docker compose up --build
```

- **API:** http://localhost:8080
- **UI:**  http://localhost:3000
- **MCP:** http://localhost:9000/mcp

> **Compose profiles:** use `--profile default` to skip Neo4j, or `--profile graph` to enable the Neo4j graph store for cartographer. See Operations Runbook below.

You can also start the example from the `workspace-py/` root using the shared dev compose:

```bash
cd workspace-py
make demo-fm_agent
```

This brings up Qdrant, PostgreSQL, the Orchid MCP gateway, and Neo4j (via the `graph` profile).

> **Planned improvements:** implementation prompts live in `.knowledge/prompts/fm-agents/features/`.

### MCP Gateway (Claude / Cursor / Cowork)

Connect the fleet to any MCP-capable host LLM. Add to your `claude_desktop_config.json` or equivalent:

```json
{
  "mcpServers": {
    "fm-agent": {
      "type": "streamableHttp",
      "url": "http://localhost:9000/mcp"
    }
  }
}
```

The fleet is exposed as five MCP tools: `orchid_ask`, `orchid_upload_file`,
`orchid_signal_emit`, `orchid_bloom_status`, `orchid_bloom_list`.

## Architecture

| Concern | Implementation |
|---------|---------------|
| Chat LLM | `gemini/gemini-flash-latest` |
| Embeddings | `gemini/gemini-embedding-001` (3072-d) |
| Vector store | Qdrant (`orchid-rag-qdrant`) |
| Graph store | Neo4j 5 (`orchid-rag-neo4j`, profile `graph`) |
| Storage | PostgreSQL (`OrchidPostgresChatStorage`) |
| Auth | service_account only for v1. No end-user identity in this example. |

## Agent Fleet (11 agents)

| Agent | Type | Namespace |
|---|---|---|
| notification-expert | RAG service expert | svc-notification |
| mailer-expert | RAG service expert | svc-mailer |
| push-expert | RAG service expert | svc-push |
| eventbus-expert | RAG service expert | svc-eventbus |
| domains-expert | RAG service expert | svc-domains |
| devops-expert | RAG service expert | svc-devops |
| messenger-expert | RAG service expert | svc-messenger |
| standards-coach | Coding standards | eng-standards |
| cartographer | Graph RAG | platform-graph |
| sre-investigator | Incident investigation (MCP) | runbooks |
| delivery-analyst | Ticket/MR context (MCP) | tickets |

## Operations Runbook

### Start / Stop

```bash
# Full stack
docker compose up --build

# Without Neo4j (skip graph profile)
docker compose --profile default up --build

# With Neo4j
docker compose --profile graph up --build

# Stop
docker compose down
```

### Reindex

```bash
# Docs pass — ingest READMEs, configs, OpenAPI specs
fm-indexer docs /path/to/repo1 /path/to/repo2 ...

# Cards pass — regenerate LLM module summaries
fm-indexer cards /path/to/repo1 ...

# Graph pass — extract platform dependency graph into Neo4j
fm-indexer graph /path/to/repo1 ...

# KB pass — crawl Help Center sections
fm-indexer kb

# Prune vectors for deleted files
fm-indexer prune /path/to/repo1 ...
```

Or via API (requires `ALLOW_INDEX_ENDPOINT=true`):
```bash
curl -X POST http://localhost:8080/indexer/run \
  -H "Content-Type: application/json" \
  -d '{"subcommand": "docs", "repo_paths": ["/path/to/repo"]}'
```

### Ingest raw Markdown exports

The framework `orchid index` command can ingest the Markdown exports under `.knowledge/prompts/fm-agents/raw-input/` with YAML front-matter parsing and idempotent re-runs.

Each Markdown file should contain a YAML front-matter block with an identifier field (e.g. `page_id`, `article_id`). The command reads the front matter, chunks the body, embeds it, and writes it to the configured Qdrant namespace.

```bash
# Confluence pages → runbooks namespace
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/confluence \
  -n runbooks \
  --front-matter \
  --id-field page_id \
  -c workspace-py/examples/fm_agent/config/orchid.yml

# KB articles → product-kb namespace
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/kb \
  -n product-kb \
  --front-matter \
  --id-field article_id \
  -c workspace-py/examples/fm_agent/config/orchid.yml
```

Available raw-input directories:

| Directory | Target namespace | Recommended id-field |
|---|---|---|
| `raw-input/confluence` | `runbooks` | `page_id` |
| `raw-input/kb` | `product-kb` | `article_id` |

Common flags:

| Flag | Purpose |
|---|---|
| `-n <namespace>` | Qdrant namespace to write into |
| `--front-matter` | Parse YAML front matter for metadata and id |
| `--id-field <key>` | Front-matter key to use as the document id |
| `--prune` | Remove vectors whose source file no longer exists |
| `--force` | Re-index even if the content hash hasn't changed |
| `--manifest-dsn <dsn>` | Use PostgreSQL for the ingestion manifest (default: SQLite) |

Re-run idempotently: unchanged files are skipped, removed files are pruned, and new or modified files are indexed.

```bash
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/confluence \
  -n runbooks \
  --front-matter \
  --id-field page_id \
  --prune \
  -c workspace-py/examples/fm_agent/config/orchid.yml
```

Use a PostgreSQL manifest backend when running in a multi-replica or CI environment:

```bash
orchid index dir \
  .knowledge/prompts/fm-agents/raw-input/confluence \
  -n runbooks \
  --front-matter \
  --id-field page_id \
  --manifest-dsn postgresql://orchid:orchid@localhost:5432/orchid \
  -c workspace-py/examples/fm_agent/config/orchid.yml
```

> **Note:** Run these commands from the workspace root (`workspace-py/`). Make sure `GEMINI_API_KEY` is exported and Qdrant is reachable.

### Add an Agent

1. Add a new entry under `agents:` in `config/agents.yaml`
2. Assign a `namespace`, `retrieval` strategy, and `topic_restriction` guardrail
3. If the agent needs MCP tools, add `mcp_servers:` with tool allowlists
4. Restart `agents-api`: `docker compose restart agents-api`
5. Re-index if the agent has a new RAG namespace: `fm-indexer docs /path/to/new-repo`

### Secrets Rotation

Secrets live in `.env` (never committed). To rotate:
1. Generate new credentials in the relevant service (GitLab, Datadog, etc.)
2. Update `.env` with the new values
3. Restart: `docker compose restart agents-api`
4. Old secrets are not cached — all auth is per-request

The `secret_detection` output guardrail (Phase 8) redacts any credential that
leaks into agent output before it reaches the user.

### Webhook Secrets

The FM Agent ingests events from external services via webhooks. Each webhook source validates incoming requests with an HMAC secret configured in `config/agents.yaml`:

```yaml
events:
  ingestion:
    sources:
      - id: datadog-webhook
        validator:
          class: orchid_ai.events.auth.HMACValidator
          secret_ref: env:DD_WEBHOOK_SECRET
      - id: gitlab-webhook
        validator:
          class: orchid_ai.events.auth.HMACValidator
          secret_ref: env:GITLAB_WEBHOOK_SECRET
```

`secret_ref: env:VAR_NAME` reads the secret from the named environment variable at startup. If a variable is unset, the API fails fast and exits. For local development the shared compose provides defaults; for real webhooks you must set the values in `.env`.

#### Obtaining `DD_WEBHOOK_SECRET`

1. Open Datadog and navigate to **Integrations → Webhooks**.
2. Create or edit a webhook and set a **Custom Headers** value or use the **Secret** field provided by Datadog for webhook authentication.
3. Copy that secret value.
4. Add it to `.env`:
   ```bash
   DD_WEBHOOK_SECRET=your-datadog-webhook-secret
   ```
5. Restart the API:
   ```bash
   docker compose restart agents-api
   ```

#### Obtaining `GITLAB_WEBHOOK_SECRET`

1. In GitLab, open the project you want to receive webhooks from.
2. Go to **Settings → Webhooks**.
3. Create a new webhook and fill in the URL: `http://your-orchid-host/signals`.
4. In the **Secret token** field, enter a strong random string (GitLab will HMAC-sign payloads with this token).
5. Save the webhook and copy the secret token you entered.
6. Add it to `.env`:
   ```bash
   GITLAB_WEBHOOK_SECRET=your-gitlab-webhook-secret
   ```
7. Restart the API:
   ```bash
   docker compose restart agents-api
   ```

For local development without real webhooks, the defaults in `workspace-py/script/docker-compose.examples.yml` are sufficient.

### Run Evals

```bash
# Generate draft Q&A pairs
python -m examples.fm_agent.evals.generate

# Code-validate against repos
python -m examples.fm_agent.evals.generate code-validate /path/to/repos/...

# Run against the API
python -m examples.fm_agent.evals.run http://localhost:8080

# Results in evals/RESULTS.md
```

### Verify Baseline

Three surfaces — same question should route correctly and cite sources:

```bash
# REST API
curl -X POST http://localhost:8080/chats -H "Content-Type: application/json" -d '{"title":"test"}'
# → use chat_id for messages

# Frontend
open http://localhost:3000

# MCP gateway
# → add to Claude/Cursor config as above, then ask via host LLM
```

## Planned Improvements

Implementation prompts for upcoming phases are tracked in `.knowledge/prompts/fm-agents/features/`. Each prompt is a self-contained work item that can be picked up independently.
