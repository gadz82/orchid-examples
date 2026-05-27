# Orchid Examples

A collection of self-contained examples showcasing every major Orchid feature. Each example lives in its own directory with its own configuration, agents, and tools.

---

## Quick start (Docker)

Five examples ship a full Docker stack and can be run independently:

```bash
cd examples/<name>
cp .env.example .env   # fill in your API key
docker compose up --build
```

| URL | Service |
|-----|---------|
| http://localhost:8080 | Agents API |
| http://localhost:3000 | Frontend UI |
| http://localhost:9000/mcp | MCP gateway |

---

## Examples

### 🐳 Docker-ready (full stack)

| Example | What it shows | Storage | Services |
|---------|---------------|---------|---------|
| [basketball](./basketball/) | Hello-world: two GenericAgents (NBA stats + psychologist), built-in tools, agent-level skills | PostgreSQL + Qdrant | API, Qdrant, Postgres, UI, MCP |
| [restaurant](./restaurant/) | Custom agent class, RAG with dynamic injection, sequential routing | SQLite + Qdrant | API, Qdrant, UI, MCP |
| [helpdesk](./helpdesk/) | Custom TicketAgent class, cross-agent skills, event-driven workflow | SQLite + Qdrant | API, Qdrant, UI, MCP |
| [education](./education/) | Quiz/lesson generation, multi-format export (PDF, PPTX), batch processing | SQLite + Qdrant | API, Qdrant, UI, MCP |
| [postgres-storage](./postgres-storage/) | `orchid-storage-postgres` plugin: PostgreSQL chat persistence + checkpointer | PostgreSQL + Qdrant | API, Qdrant, Postgres, UI, MCP |

---

### Agents & multi-agent patterns

| Example | What it shows |
|---------|---------------|
| [travel-agency](./travel-agency/) | Multi-agent travel planner: flights, hotels, bookings |
| [architecture_review](./architecture_review/) | Three-agent design review board with cross-agent orchestrator skills |
| [festival-producer](./festival-producer/) | Three-agent event production (booking, logistics, marketing) with `rag_augmented` memory |
| [car_dealer_fleet](./car_dealer_fleet/) | Dynamic agent fleet generated at runtime from content sources |
| [tech_conference](./tech_conference/) | Four-agent conference assistant (venue, schedule, visitor, speaker) |
| [hospital_front_office](./hospital_front_office/) | Four-agent hospital front-office assistant |
| [orchid_experts](./orchid_experts/) | Ten RAG-powered expert agents, one per Orchid package |

### RAG & knowledge

| Example | What it shows |
|---------|---------------|
| [wiki](./wiki/) | Two-agent RAG demo with namespace-scoped retrieval |
| [recipes](./recipes/) | Zero-infrastructure RAG using ChromaDB (no Docker/Qdrant needed) |
| [graph_kb](./graph_kb/) | GraphRAG strategy (`InMemoryGraphStore`) with org-chart corpus |
| [gallery-curator](./gallery-curator/) | Layered conversation memory and `rag_augmented` summarization |
| [rag-strategies](./rag-strategies/) | Four agents, same knowledge base, four different `OrchidRetrievalStrategy` |
| [car-dealer-local](./car-dealer-local/) | RAG from local filesystem (no startup hook, no Qdrant) |

### Tools & strategies

| Example | What it shows |
|---------|---------------|
| [tool-strategies](./tool-strategies/) | `tool_call_strategy` (all / sequential / llm_decides) + custom strategy |

### Configuration & extensibility

| Example | What it shows |
|---------|---------------|
| [prompt-customization](./prompt-customization/) | Every supervisor and agent prompt extension point |
| [md-config](./md-config/) | Markdown-based agent configuration (alternative to YAML) |
| [custom-storage](./custom-storage/) | Custom `OrchidChatStorage` implementation (JSON-file backend) |
| [api-extensions](./api-extensions/) | Adding custom FastAPI endpoints to orchid-api |
| [mcp-auth](./mcp-auth/) | All three MCP auth modes: `none`, `passthrough`, `oauth` |

### Async & scheduled workflows

| Example | What it shows |
|---------|---------------|
| [learning](./learning/) | Cron-triggered fan-out: one tick → parallel per-user Bloom runs |

### Embedding Orchid in your own code

| Example | What it shows |
|---------|---------------|
| [embedded-python](./embedded-python/) | Call Orchid directly from Python (no HTTP, no CLI) |
| [embedded-api](./embedded-api/) | Mount orchid-api into an existing FastAPI application |

---

## Requirements

- **Docker** — for the Docker-ready examples
- **Python 3.11+** — for running examples directly (non-Docker)
- **API key** — Gemini (free tier at [aistudio.google.com](https://aistudio.google.com/apikey)), or Groq / Anthropic / OpenAI
- **Ollama** (optional) — for fully local inference (`ollama pull llama3.2 nomic-embed-text`)

---

## Shared Docker helpers

The `_docker/` directory contains Dockerfiles shared across all Docker-ready examples:

| File | Purpose |
|------|---------|
| `_docker/Dockerfile.frontend` | Clones and runs [orchid-frontend](https://github.com/gadz82/orchid-frontend) |
| `_docker/Dockerfile.mcp` | Runs the MCP gateway via `npm install @orchid-ai/mcp` |
