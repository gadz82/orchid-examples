---
# Orchid — MD Config Demo
#
# Self-contained demo: basketball + psychologist agents with SQLite storage.
# No MCP servers or external APIs required.
#
# Usage:
#   ORCHID_CONFIG=examples/md-config/orchid.md uvicorn orchid_api.main:app
#
# Or via docker-compose:
#   docker compose -f docker-compose.md-config.yml up --build
#
# This is a Markdown config file. The YAML frontmatter (between ---) holds
# structured config fields. The body (after the second ---) is free-form
# documentation — it is ignored at runtime for the root config.

# ── Infrastructure keys (previously orchid.yml) ──────────────
agents:
  config_format: md
  agents_dir: agents

llm:
  model: ollama/llama3.2
  ollama_api_base: http://host.docker.internal:11434

auth:
  dev_bypass: true

rag:
  vector_backend: qdrant
  qdrant_url: http://qdrant:6333
  embedding_model: ollama/nomic-embed-text

upload:
  vision_model: ollama/minicpm-v
  namespace: uploads
  max_size_mb: 20
  chunk_size: 1000
  chunk_overlap: 200

storage:
  class: orchid_ai.persistence.sqlite.OrchidSQLiteChatStorage
  dsn: /data/chats.db

tracing:
  langsmith_tracing: false

# ── Agent behavior keys (previously agents.yaml top-level) ──
version: "1"

defaults:
  llm:
    model: ollama/llama3.2
    temperature: 0.2
  rag:
    enabled: false

supervisor:
  assistant_name: "Basketball AI"

# ── Global guardrails ────────────────────────────────────────
guardrails:
  input:
    - type: prompt_injection
      fail_action: block
    - type: content_safety
      fail_action: block
    - type: max_length
      fail_action: block
      config:
        max_characters: 5000
  output:
    - type: pii_detection
      fail_action: redact
      config:
        entities: [email, phone, ssn]

# ── Built-in tools ────────────────────────────────────────────
tools:
  get_player_stats:
    class: examples.basketball.tools.basketball.GetPlayerStatsTool
    description: "Get stats for an NBA player (points, rebounds, assists, team, position)"
  compare_players:
    class: examples.basketball.tools.basketball.ComparePlayersTool
    description: "Side-by-side comparison of two NBA players with advantage analysis"
  get_team_roster:
    class: examples.basketball.tools.basketball.GetTeamRosterTool
    description: "Get all players on a given NBA team"
  assess_motivation:
    class: examples.basketball.tools.psychology.AssessMotivationTool
    description: "Assess a player's motivation level, drive type, and risk factors"
  suggest_mental_strategy:
    class: examples.basketball.tools.psychology.SuggestMentalStrategyTool
    description: "Suggest mental performance strategies for a given situation (e.g. slump, pressure)"
  analyze_team_dynamics:
    class: examples.basketball.tools.psychology.AnalyzeTeamDynamicsTool
    description: "Analyze team chemistry, cohesion, and group motivation patterns"

# ── Orchestrator-level skills (cross-agent) ───────────────────
skills:
  player_performance_review:
    description: >
      Get a player's stats and performance data, then assess their
      motivation and mental state with actionable recommendations.
    steps:
      - agent: basketball
        instruction: "Look up the player's current stats and performance data"
      - agent: psychologist
        instruction: "Based on the player's stats and situation, assess their motivation and suggest mental strategies"

  team_wellness_check:
    description: >
      Review a team's full roster and then analyze group dynamics,
      cohesion, and motivation across the team.
    steps:
      - agent: basketball
        instruction: "Get the full roster for the specified team with all player stats"
      - agent: psychologist
        instruction: "Analyze the team's dynamics, cohesion, and suggest group motivation strategies"

# ── Pollen + Bloom (events) ──────────────────────────────────
events:
  enabled: true
  store:
    class: orchid_ai.events.backends.sqlite.SQLiteEventStorage
    extra_args:
      dsn: /data/chats.db
  queue:
    class: orchid_ai.events.queues.sqlite.SQLiteSignalQueue
    poll_interval_ms: 200
    lease_seconds: 30
    max_attempts: 3
  scheduler:
    class: orchid_ai.events.schedulers.apscheduler.APSchedulerBackend
  producers:
    - class: orchid_ai.events.producers.scheduler.SchedulerProducer
    - class: orchid_ai.events.producers.internal.InternalEmissionProducer
  processors:
    - class: orchid_ai.events.processors.asyncio_pool.AsyncioWorkerPoolProcessor
      concurrency: 1
  schedules:
    - id: morning-trivia-cron
      cron: "0 7 * * 1-5"
      trigger_id: morning-trivia
      identity: { mode: service_account, name: trivia-bot }
  triggers:
    - id: morning-trivia
      "on": { signal: cron, cron: "0 7 * * 1-5" }
      emits:
        agent: notifications
        prompt_template: |
          Produce a 3-fact NBA trivia digest based on yesterday's games.
          Each fact must cite the source game.  Format as Markdown.
        identity: { mode: service_account, name: trivia-bot }
        visibility: tenant
      retry: { max: 2, backoff: exponential }
      parallelism: unbounded

mcp_gateway: {}
---
