# Orchid — MD Configuration Demo

This example demonstrates the **Markdown-based configuration** system
added in [ADR-030](../../.knowledge/adr/ADR-030-md-configuration.md).

Instead of two YAML files (`orchid.yml` + `agents.yaml`), the MD config
uses a single `orchid.md` root file with YAML frontmatter + per-agent
Markdown files in `agents/`.  The Markdown body of each agent file is
used directly as the system prompt — no YAML multi-line string escaping.

## File Layout

```
examples/md-config/
├── orchid.md                  ← Unified root config (replaces orchid.yml + agents.yaml)
├── agents/
│   ├── basketball.md          ← Basketball expert agent
│   ├── psychologist.md        ← Sports psychologist agent
│   └── notifications.md       ← Trivia generator (Pollen + Bloom)
├── orchid.yml                 ← Fallback YAML (identical config for comparison)
├── agents.yaml                ← Fallback YAML agents config
├── test_equivalence.py        ← Verifies MD == YAML output
└── README.md                  ← This file
```

## Running

```bash
# From the repo root:
ORCHID_CONFIG=examples/md-config/orchid.md uvicorn orchid_api.main:app --port 8000

# Via Docker:
docker compose -f docker-compose.md-config.yml up --build
```

## Config Format

Each `.md` file has two sections separated by `---`:

1. **YAML frontmatter** — Structured fields (description, tools, RAG, skills, etc.)
2. **Markdown body** — The agent's system prompt (rich Markdown, no YAML escaping)

Example:
```markdown
---
description: "Basketball expert"
tools:
  - get_player_stats
  - compare_players
---

# Basketball Expert

You are a basketball statistics expert.
Focus on player performance metrics.
```

## Equivalence

The MD and YAML configs produce identical `OrchidAgentsConfig` output.
Run the equivalence test to verify:

```bash
cd orchid && .venv/bin/python examples/md-config/test_equivalence.py
```

## Hot-Reload

When running via `orchid-api` with `ORCHID_RELOAD_INTERVAL=30` (default),
any edit to `orchid.md` or `agents/*.md` is detected within 30 seconds
and the graph is rebuilt without a restart.
