# Car Dealer — Dynamic Expert Agent Fleet

A car dealership system where **specialised expert agents are created
dynamically from content sources**.  No agents are defined in YAML — the
entire fleet is generated at bootstrap using an **ephemeral Orchid instance**
that analyses specification documents.

## What It Demonstrates

- **Orchid-powered fleet generation** — the startup hook creates a programmatic,
  ephemeral Orchid instance with reader + summariser agents that collaborate
  via the full Orchid pipeline (supervisor routing, skills, tools, agentic
  tool-calling loop) to analyse content and produce expert agent configs.
- **Python-configured agents** — reader and summariser are defined entirely in
  Python code (`hooks/startup.py`), not in `agents.yaml`.  They are real
  Orchid agents that go through the graph, not simple helper functions.
- **Content → Orchid → Fleet** — the pipeline is: content sources → ephemeral
  Orchid (reader → summariser via skill) → JSON agent configs → SQLite
  → `merge_from_db()` → compiled graph with N specialised experts.
- **Framework-level SQLite config storage** — uses `OrchidSQLiteConfigStorage`
  for ``OrchidConfigStorage`` (SQLite built-in; PostgreSQL config storage
  available via orchid-storage-postgres plugin).
- **Clean slate on every bootstrap** — existing agents are deleted and recreated,
  so adding/removing documents automatically reshapes the fleet.
- **Self-contained experts** — each generated agent carries its domain knowledge
  directly in its system prompt; no RAG or tools needed for basic queries.

## Fleet generation flow

```
Orchid bootstrap
│
├─ Startup hook (hooks/startup.py)
│  │
│  ├─ 1. Delete existing agents from SQLite (clean slate)
│  │
│  ├─ 2. Build ephemeral OrchidAgentsConfig programmatically:
│  │      • reader agent — uses list_content_files + read_content_file tools
│  │      • summariser agent — analyses reader output, generates JSON configs
│  │      • build_expert_fleet skill — orchestrates reader → summariser
│  │
│  ├─ 3. Build ephemeral OrchidRuntime with content_sources
│  │
│  ├─ 4. build_graph() → ephemeral LangGraph graph
│  │
│  ├─ 5. graph.ainvoke("Read all documents and create expert agents")
│  │      Supervisor routes to build_expert_fleet skill:
│  │        Step 1 → reader agent: discovers and reads 6 documents
│  │        Step 2 → summariser agent: analyses and outputs JSON array
│  │
│  └─ 6. Extract JSON configs from conversation, persist to SQLite
│
└─ merge_from_db() picks up agents → toyota-expert, ford-expert,
   vw-expert, audi-expert, honda-expert, bmw-expert are compiled
   into the graph
```

## How It Works

The startup hook runs **before** `merge_from_db()`, so agents created in the
same bootstrap cycle are available immediately — no restart needed.

On every subsequent bootstrap, existing agents are deleted and recreated,
ensuring the fleet always reflects the current content sources.

## Prerequisites

- Ollama running with `llama3.2`
- `pip install -e ../orchid -e ../orchid-cli`

## Usage

```bash
pip install -e orchid -e orchid-cli

# First run — the startup hook builds the fleet
orchid chat interactive --config examples/car-dealer-fleet/orchid.yml

# The supervisor routes queries to the right expert:
> What's the fuel economy of the Toyota Camry?
> What engine options does the BMW 3 Series have?
> Compare the Audi A4 and Honda Accord warranties.
> Which vehicles have Adaptive Cruise Control?
```

## File Layout

```
examples/car-dealer-fleet/
├── README.md                   # This file
├── __init__.py
├── orchid.yml                  # content_sources + config_storage + startup hook
├── agents.yaml                 # Empty agents {} + config_storage enabled
├── data/                       # 6 car specification documents
│   ├── camry-2025-specs.md     # Toyota Camry
│   ├── f150-2025-specs.md      # Ford F-150
│   ├── golf-2025-specs.txt     # Volkswagen Golf
│   ├── audi-a4-2025-specs.md   # Audi A4
│   ├── honda-accord-2025-specs.md  # Honda Accord
│   └── bmw-3-series-2025-specs.md  # BMW 3 Series
├── hooks/
│   ├── __init__.py
│   └── startup.py              # Ephemeral Orchid fleet builder
└── tests/
    ├── __init__.py
    └── test_fleet.py           # 13 tests (content, JSON parsing, SQLite, config)
```

## Running Tests

```bash
cd examples/car-dealer-fleet
python -m pytest tests/ -x -v  # all 13 tests
```

Tests cover content source discovery, JSON extraction from LLM-like output,
SQLite helpers (clear + persist), `OrchidConfigStorageConfig` defaults, and
`OrchidSQLiteConfigStorage` CRUD.
