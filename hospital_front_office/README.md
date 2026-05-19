# Hospital Front-Office Example — RAG-Based Multi-Agent System

A hospital front-office assistant demonstrating **RAG-based knowledge ingestion**, **multi-agent coordination**, and **cross-agent skills** for patient and visitor support. Four `GenericAgent` instances coordinate via a LangGraph supervisor to handle wayfinding, bureaucracy, scheduling, and emergency triage. No MCP servers, no external APIs, and no custom Python agent classes required.

## What It Demonstrates

- **GenericAgent with RAG** — Four agents (`department-navigator`, `bureaucracy-procedures`, `opening-hours`, `emergency-triage`) each with dedicated RAG namespaces ingesting markdown knowledge files
- **Cross-agent skills** — The `indications-and-hours` skill combines department location with opening hours for unified responses
- **Supervisor routing** — LangGraph supervisor automatically routes queries to the appropriate agent based on content
- **SQLite persistence** — File-based SQLite storage at `/data/hospital_chats.db`
- **Local LLM via Ollama** — Uses `ollama/llama3.2` for completions and `ollama/nomic-embed-text` for embeddings
- **Dummy identity resolver** — `HospitalIdentityResolver` provides in-memory auth for local development

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Agent definition | `GenericAgent` via YAML only |
| RAG | Qdrant with 4 namespaces (departments, bureaucracy, opening-hours, emergency) |
| Skills | Cross-agent `indications-and-hours` skill |
| Storage | SQLite (shared with basketball example) |
| LLM | Ollama (`llama3.2`, `nomic-embed-text`) |
| Auth | Dummy identity resolver (in-memory) |

## Prerequisites

- Ollama running with models:
  ```bash
  ollama pull llama3.2
  ollama pull nomic-embed-text
  ollama pull minicpm-v
  ```
- Python 3.11+ with `orchid-ai` and `orchid-cli` installed

## Usage

### Via Docker Compose

```bash
# From repo root
docker compose -f docker-compose.demo.yml up --build
```

### Via Standalone API

```bash
pip install -e orchid -e orchid-api
ORCHID_CONFIG=examples/hospital_front_office/orchid.yml uvicorn orchid_api.main:app --port 8000
```

### Via CLI

```bash
pip install -e orchid -e orchid-cli

# Interactive session
orchid chat interactive --config examples/hospital_front_office/orchid.yml

# Ask about a department location
orchid chat send "Where is cardiology?" \
  --config examples/hospital_front_office/orchid.yml

# Ask about bureaucracy
orchid chat send "How do I get my medical records?" \
  --agent bureaucracy-procedures \
  --config examples/hospital_front_office/orchid.yml

# Ask about emergency triage
orchid chat send "I have chest pain, what should I do?" \
  --agent emergency-triage \
  --config examples/hospital_front_office/orchid.yml
```

## File Layout

```
examples/hospital_front_office/
├── orchid.yml              # Top-level config (LLM, storage, RAG, startup hook)
├── agents.yaml             # Four agents + cross-agent skills
├── identity.py             # Dummy OAuth identity resolver
├── README.md
├── hooks/
│   ├── startup.py          # Seeds knowledge/*.md into Qdrant
│   └── __init__.py
├── knowledge/
│   ├── departments/        # 12 department location files
│   ├── bureaucracy/        # 10 procedure/administration files
│   ├── opening-hours/      # 7 schedule/hours files
│   └── emergency/          # 5 triage/emergency files
└── tests/
    ├── test_hospital_startup.py
    └── __init__.py
```

## Agents

| Agent | Purpose | RAG Namespace |
|-------|---------|---------------|
| `department-navigator` | Floor, wing, directions, accessibility | `departments` |
| `bureaucracy-procedures` | Registration, documents, certificates | `bureaucracy` |
| `opening-hours` | Visiting times, schedules, exceptions | `opening-hours` |
| `emergency-triage` | Self-triage, triage codes, 118 guidance | `emergency` |

## Cross-Agent Skills

### indications-and-hours
Combines department location with opening hours. Activated when a user asks about visiting a department and needs both WHERE to go and WHEN.

**Workflow:**
1. `department-navigator` provides floor, wing, stairs, elevator, directions
2. `opening-hours` provides visit times, booking requirements, exceptions
3. Unified response with location + timing

## Sample Interaction

```
User: Where is cardiology and when can I visit?
Assistant: [cross-agent skill activates]
**Cardiology Department**
**Where:** 2nd Floor, Wing A
- From main entrance: Turn right at the information desk, take Stair A or Elevator A2 to the 2nd floor...
**Opening Hours:**
- Monday to Friday: 08:00-13:00, 14:00-18:00
- Booking required for visits

User: I have chest pain, what should I do?
Assistant: [routes to emergency-triage]
This is a self-triage guide and does NOT replace professional medical evaluation.
Based on your symptom (chest pain), this is classified as Code ORANGE - Urgent.
Wait time: < 15 minutes. Proceed to the Emergency Department immediately.

User: How do I get my medical records?
Assistant: [routes to bureaucracy-procedures]
To request your medical records:
1. Go to the Medical Records Office — Ground Floor, Wing D, Window 3
2. Bring: Valid ID, Tessera sanitaria, Completed request form
3. Office hours: Monday-Friday, 09:00-12:00
4. Processing time: 7-15 business days
```

## Contrast with Other Examples

| Example | Agents | RAG | Skills | Custom Code |
|---------|--------|-----|--------|-------------|
| basketball | 2 | Optional | Cross-agent | SQLite storage + tools |
| **hospital** | **4** | **Yes (4 namespaces)** | **Cross-agent** | **None (YAML + MD only)** |
| restaurant | 3 | Yes (dynamic) | Cross-agent | Custom agent class |

## Next Steps

After exploring the hospital demo, try:
- **tech-conference** — Similar RAG pattern with venue/schedule/visitor/speaker agents
- **restaurant** — Custom agent class with dynamic RAG injection
- **helpdesk** — Event-driven workflows with Pollen + Bloom
