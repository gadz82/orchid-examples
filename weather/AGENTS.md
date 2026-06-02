# Weather Example — Agents.md

## Overview

Multi-agent weather fleet demonstrating remote MCP integration, PostgreSQL storage, and RAG chat summarization in the Orchid framework.

### Agents (3)

| Agent | Type | Tools | Description |
|-------|------|-------|-------------|
| **weather-forecast** | GenericAgent (YAML) | Remote MCP: `get_forecast`, `get_current_weather` | Fetches live weather data from Open-Meteo API |
| **weather-alerts** | GenericAgent (YAML) | MCP + builtin: `get_safety_tips`, `assess_weather_risk` | Detects extreme weather, suggests safety measures |
| **outfit-advisor** | OutfitAdvisorAgent (custom) | Builtin: `recommend_outfit` + RAG | Recommends clothing based on weather data + RAG guides |

### Key Features Demonstrated

1. **Remote MCP server** — `weather-mcp` runs as a separate Docker service, wrapping the free Open-Meteo API. Configured as `type: remote` with `auth.mode: none`.
2. **PostgreSQL storage** — Uses `orchid-storage-postgres` plugin for chat persistence.
3. **RAG chat summarization** — Sliding-window compression (`history_summary_enabled: true`) compresses older conversation turns via LLM summary.
4. **Combo tools** — Built-in Python tools (`clothing.py`, `safety.py`) + MCP-delegated tools from the weather server.
5. **Cross-agent skills** — `prepare_for_day` (forecast → alerts → outfit) and `emergency_check` (forecast → alerts).
6. **Custom agent subclass** — `OutfitAdvisorAgent` demonstrates reading sibling agent results from `state["mcp_context"]` and using inherited helpers (`fetch_rag_context`, `extract_conversation_history`, `summarise`).
7. **Startup RAG seeding** — Clothing guides and safety guides seeded into Qdrant at startup via `hooks/startup.py`.

## Running

```bash
cd examples/weather
cp .env.example .env   # fill in GEMINI_API_KEY
docker compose up --build

# API: http://localhost:8080
# UI:  http://localhost:3000
# MCP: http://localhost:9000/mcp
# Weather MCP: http://localhost:3002/health
```

### Standalone (no Docker)

```bash
# Start the weather MCP server in a separate terminal:
cd examples/weather/mcp-weather && npm install && node index.js

# Start the API:
ORCHID_CONFIG=examples/weather/orchid.yml GEMINI_API_KEY=... uvicorn orchid_api.main:app --port 8000
```

## Testing

```bash
cd examples/weather && pytest tests/ -x
```

## File Map

```
examples/weather/
├── orchid.yml                    # Runtime config (LLM, storage, RAG, startup hook)
├── agents.yaml                   # Agent definitions + builtin tools + skills
├── docker-compose.yml            # 6-service stack
├── Dockerfile                    # API image (gcc for asyncpg)
├── Dockerfile.mcp-weather        # Weather MCP server image
├── requirements.txt              # Python deps
├── pyproject.toml                # Package metadata
├── .env.example                  # Environment template
├── identity.py                   # WeatherIdentityResolver
├── agents/
│   └── outfit.py                 # OutfitAdvisorAgent (custom OrchidAgent subclass)
├── tools/
│   ├── clothing.py               # RecommendOutfitTool
│   └── safety.py                 # GetSafetyTipsTool, AssessWeatherRiskTool
├── hooks/
│   └── startup.py                # RAG seed: clothing guides + safety guides
├── mcp-weather/
│   ├── package.json              # MCP server deps
│   └── index.js                  # MCP server — Open-Meteo wrapper
└── tests/
    ├── conftest.py               # Pytest config + fixtures
    └── test_weather_e2e.py       # Config + tool + agent integration tests
```
