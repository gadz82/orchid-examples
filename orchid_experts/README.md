# Orchid Experts — RAG-powered Knowledge Base Example

A self-contained demo deploying a **fleet of ten RAG-powered expert agents**, each the chief of knowledge for one orchid-* package or cross-cutting concept. Every agent is a `GenericAgent` (zero custom Python agent code) that answers deep questions from pre-ingested markdown knowledge files.

## What It Demonstrates

- **10 domain-specialized RAG agents** — pure YAML + Markdown, no Python agent code.
- **10 RAG namespaces** — one per domain, with 86 knowledge files covering every Orchid concept.
- **9 cross-agent skills** — sequential agent chains for multi-domain questions.
- **Guardrails** — global input/output guards + per-agent topic restrictions.
- **Startup hook** — auto-seeds all knowledge files into Qdrant at process startup.

## Features

| Feature | Detail |
|---------|--------|
| Agents | 10 (all `GenericAgent`) |
| Custom Python code | Zero (YAML + MD only) |
| RAG namespaces | 10 |
| Knowledge files | 86 markdown files |
| Cross-agent skills | 9 |
| Guardrails | Global + per-agent topic_restriction |
| MCP servers | None (pure RAG example) |
| Auth | Trivial any-bearer resolver |

## Prerequisites

- **Python 3.11+** with `orchid-ai` installed.
- **Ollama** running with models: `llama3.2`, `nomic-embed-text`, `minicpm-v`.
- **Docker** (for Qdrant and the API container).

## Usage

### Docker Compose

```bash
docker compose -f docker-compose.demo.yml up --build
```

The startup hook automatically seeds all 86 knowledge files into Qdrant.

### Standalone API

```bash
ORCHID_CONFIG=examples/orchid_experts/orchid.yml uvicorn orchid_api.main:app --port 8000
```

### CLI

```bash
# Send a single question
orchid chat send "What ABCs does orchid define?" \
  --config examples/orchid_experts/orchid.yml

# Interactive conversation
orchid chat interactive \
  --config examples/orchid_experts/orchid.yml
```

## File Layout

```
examples/orchid_experts/
├── __init__.py
├── orchid.yml                    # Runtime config (Qdrant, SQLite, Ollama)
├── agents.yaml                   # 10 agents + supervisor + skills + guardrails
├── identity.py                   # ExpertsIdentityResolver
├── hooks/
│   ├── __init__.py
│   └── startup.py                # Seeds knowledge → Qdrant
├── knowledge/
│   ├── ai-integration/           (10 files)   Production deployment patterns
│   ├── auth-system/              (9 files)    OAuth, OIDC, DCR, identity
│   ├── bloom-events/             (8 files)    Pollen+Bloom event system
│   ├── mcp-system/               (7 files)    MCP protocol + gateway
│   ├── orchid-api-pkg/           (8 files)    FastAPI server package
│   ├── orchid-cli-pkg/           (9 files)    CLI package
│   ├── orchid-framework/         (12 files)   Core framework ABCs + concepts
│   ├── orchid-frontend-pkg/      (8 files)    Next.js frontend package
│   ├── rag-system/               (9 files)    RAG scopes, strategies, backends
│   └── tools-skills/             (6 files)    Built-in tools + skill system
├── tests/
│   ├── __init__.py
│   └── test_orchid_experts.py    # 6 tests (identity + YAML validation)
└── README.md                     # This file
```

## Agents

| Agent | Purpose | RAG Namespace |
|-------|---------|--------------|
| `orchid` | Core framework: ABCs, config, GenericAgent, supervisor, persistence | `orchid-framework` |
| `rag` | RAG system: scopes, ingestion, retrieval, backends, hybrid search | `rag-system` |
| `tools-skills` | Tools & skills: decorators, strategies, skill execution | `tools-skills` |
| `mcp` | MCP protocol: servers, auth modes, discovery, gateway | `mcp-system` |
| `auth` | Authorization: OAuth, OIDC, DCR, identity resolution | `auth-system` |
| `bloom` | Pollen+Bloom events: signals, triggers, schedules, jobs | `bloom-events` |
| `orchid-api` | FastAPI server: routers, streaming, endpoints, plugins | `orchid-api-pkg` |
| `orchid-cli` | CLI: commands, interactive mode, ChromaDB, indexing | `orchid-cli-pkg` |
| `orchid-frontend` | Next.js UI: components, NextAuth, SSE proxy, theming | `orchid-frontend-pkg` |
| `ai-integration` | Production deployment: LLM selection, scaling, observability | `ai-integration` |

## Cross-Agent Skills

| Skill | Agents | Triggering Question |
|-------|--------|---------------------|
| `secure-deployment` | orchid → auth → ai-integration | "How do I secure my Orchid deployment?" |
| `rag-production` | rag → ai-integration | "How do I deploy RAG in production?" |
| `cli-rag-workflow` | orchid-cli → rag | "How do I use the CLI to index documents for RAG?" |
| `api-frontend-flow` | orchid-frontend → orchid-api | "How do I connect the frontend to the API?" |
| `full-mcp-stack` | mcp → auth → orchid-api | "How do I set up MCP with OAuth end-to-end?" |
| `bloom-api-integration` | bloom → orchid-api | "How do I set up Pollen+Bloom events?" |
| `frontend-auth-flow` | orchid-frontend → auth | "How does the frontend handle OAuth tokens?" |
| `framework-extend` | orchid → tools-skills | "How do I create a custom agent with custom tools?" |
| `production-observability` | orchid-api → ai-integration | "How do I monitor my Orchid deployment?" |

## Sample Interactions

### Framework Question → `orchid` Agent

```
User: What ABCs does orchid define?

Orchid Framework Expert: The orchid-ai/core/ module defines these ABCs:
  1. OrchidAgent — agent identity, run(), summarise(), fetch_rag_context()
  2. OrchidIdentityResolver — bearer token → OrchidAuthContext
  3. OrchidMCPToolCaller / OrchidMCPDiscoverable — MCP interaction
  4. OrchidVectorReader / OrchidVectorWriter — vector store access
  5. OrchidChatStorage — chat session + message persistence
  ...
```

### RAG Question → `rag` Agent

```
User: Explain the 5-level scope hierarchy

RAG System Expert: The OrchidRAGScope defines a 5-level hierarchy:
  root (__shared__) → tenant → user → chat → agent
  Each level inherits visibility from parent levels...
```

### Cross-Agent Skill → Chains `frontend` → `auth`

```
User: How do I set up OAuth with the frontend?

[Skill: frontend-auth-flow activated]
→ orchid-frontend: "Explain NextAuth v5 OIDC discovery..."
→ auth: "Explain how the API resolves bearer tokens via OrchidIdentityResolver..."
[Supervisor synthesizes response]
```

### Production Question → `ai-integration` Agent

```
User: Which LLM provider should I use in production?

AI Integration Expert: Recommendations depend on your requirements:
  - Best quality: OpenAI GPT-4o or Anthropic Claude Sonnet
  - Best cost: Google Gemini Flash or Ollama Llama 3.2 (free)
  - Best latency: Groq Llama 3.3
  - Privacy: Ollama (fully local)
  Consider a multi-model strategy with fallback...
```

## Contrast with Other Examples

| Example | Agents | Custom Code | RAG | MCP | Skills |
|---------|--------|-------------|-----|-----|--------|
| basketball | 3 | SQLite storage | No | Yes | No |
| hospital_front_office | 4 | None | Yes | No | 1 |
| tech_conference | 4 | None | Yes | No | 2 |
| **orchid_experts** | **10** | **None** | **Yes (86 files)** | **No** | **9** |

## Next Steps

- Add your own domain-specific agents by editing `agents.yaml`.
- Write additional knowledge files in the relevant `knowledge/` namespace.
- Customize guardrails for your production environment.
- Explore other examples: `restaurant/` (dynamic injection), `helpdesk/` (Pollen+Bloom), `tool-strategies/`.
