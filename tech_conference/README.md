# Tech Conference Example — RAG-Based Multi-Agent System

A tech conference assistant demonstrating **RAG-based knowledge ingestion**, **multi-agent coordination**, and **cross-agent skills** for visitor and speaker support. Four `GenericAgent` instances coordinate via a LangGraph supervisor to handle venue navigation, schedule content, visitor services, and speaker logistics. No MCP servers, no external APIs, and no custom Python agent classes required.

## What It Demonstrates

- **GenericAgent with RAG** — Four agents (`venue-navigator`, `schedule-content`, `visitor-services`, `speaker-services`) each with dedicated RAG namespaces ingesting markdown knowledge files
- **Cross-agent skills** — Two skills (`directions-and-sessions`, `speaker-logistics`) combine venue, schedule, and speaker information for unified responses
- **Supervisor routing** — LangGraph supervisor automatically routes queries to the appropriate agent based on content
- **SQLite persistence** — File-based SQLite storage at `/data/conference_chats.db`
- **Local LLM via Ollama** — Uses `ollama/llama3.2` for completions and `ollama/nomic-embed-text` for embeddings
- **Dummy identity resolver** — `ConferenceIdentityResolver` provides in-memory auth for local development

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Agent definition | `GenericAgent` via YAML only |
| RAG | Qdrant with 4 namespaces (venue, schedule, visitor-services, speaker-services) |
| Skills | Two cross-agent skills (`directions-and-sessions`, `speaker-logistics`) |
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
ORCHID_CONFIG=examples/tech_conference/orchid.yml uvicorn orchid_api.main:app --port 8000
```

### Via CLI

```bash
pip install -e orchid -e orchid-cli

# Interactive session
orchid chat interactive --config examples/tech_conference/orchid.yml

# Ask about a session location
orchid chat send "Where is the AI agents keynote and when does it start?" \
  --config examples/tech_conference/orchid.yml

# Ask about visitor services
orchid chat send "Where can I get food and is there vegetarian food?" \
  --agent visitor-services \
  --config examples/tech_conference/orchid.yml

# Ask as a speaker
orchid chat send "I'm speaking on Day 1, what do I need to do?" \
  --agent speaker-services \
  --config examples/tech_conference/orchid.yml
```

## File Layout

```
examples/tech_conference/
├── orchid.yml              # Top-level config (LLM, storage, RAG, startup hook)
├── agents.yaml             # Four agents + cross-agent skills
├── identity.py             # Dummy OAuth identity resolver
├── README.md
├── hooks/
│   ├── startup.py          # Seeds knowledge/*.md into Qdrant
│   └── __init__.py
├── knowledge/
│   ├── venue/              # 12 venue/room location files
│   ├── schedule/           # 8 schedule/session files
│   ├── visitor-services/   # 9 visitor service files
│   └── speaker-services/   # 10 speaker service files
└── tests/
    ├── test_conference_startup.py
    └── __init__.py
```

## Agents

| Agent | Purpose | RAG Namespace |
|-------|---------|---------------|
| `venue-navigator` | Room locations, directions, facilities, Wi-Fi | `venue` |
| `schedule-content` | Session schedules, speaker bios, track info | `schedule` |
| `visitor-services` | Registration, food, accessibility, transport | `visitor-services` |
| `speaker-services` | Check-in, AV specs, slide submission, green room | `speaker-services` |

## Cross-Agent Skills

### directions-and-sessions
Combines venue directions with session schedule and content. Activated when a user asks about attending a session and needs both WHERE to go and WHAT/WHEN it is.

**Workflow:**
1. `schedule-content` provides time, date, room, description, speaker bio
2. `venue-navigator` provides room location, directions, capacity, nearby facilities
3. Unified response with session info + directions

### speaker-logistics
Combines speaker services, venue navigation, and schedule content for complete speaker logistics briefing.

**Workflow:**
1. `speaker-services` provides check-in process, green room info, AV specs
2. `venue-navigator` provides room and green room directions
3. `schedule-content` provides session time and rehearsal slot
4. Complete speaker checklist response

## Sample Interaction

```
User: Where is the AI agents keynote and when does it start?
Assistant: [cross-agent skill activates]
**Keynote: The Future of AI Agents**
**When:** Monday, June 15 — 09:30 to 10:30
**Speaker:** Dr. Sarah Chen — AI researcher and author of "Agent Architectures," former lead at DeepMind.
**Where:** Main Hall, Ground Floor, Central Zone
- From registration desk: Walk straight through the main corridor, the Main Hall is directly ahead.

User: I'm speaking on Day 1, what do I need to do?
Assistant: [cross-agent skill activates]
**Speaker Checklist — Day 1**
**Your Session:** Building Production RAG Systems
**Room:** Room A (1st Floor, North Wing)
**Time:** 11:00 - 11:45
**Rehearsal Slot:** 10:30 in Room A
**Check-In:** Go to Speaker Registration Desk — 2nd Floor, VIP Zone...

User: Where can I get food and is there vegetarian food?
Assistant: [routes to visitor-services]
**Food & Beverage at TechConf 2026**
**Lunch:** Exhibition Hall, Ground Floor, South Wing, 12:00-13:30
Hot buffet with vegetarian, vegan, and gluten-free clearly labeled...
```

## Contrast with Other Examples

| Example | Agents | RAG | Skills | Custom Code |
|---------|--------|-----|--------|-------------|
| basketball | 2 | Optional | Cross-agent | SQLite storage + tools |
| hospital | 4 | Yes (4 namespaces) | Cross-agent | None (YAML + MD only) |
| **tech-conf** | **4** | **Yes (4 namespaces)** | **2 cross-agent** | **None (YAML + MD only)** |
| restaurant | 3 | Yes (dynamic) | Cross-agent | Custom agent class |

## Next Steps

After exploring the tech conference demo, try:
- **hospital-front-office** — Similar RAG pattern with hospital wayfinding/bureaucracy/triage agents
- **restaurant** — Custom agent class with dynamic RAG injection
- **helpdesk** — Event-driven workflows with Pollen + Bloom
