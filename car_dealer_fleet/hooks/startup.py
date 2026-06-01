"""Startup hook — builds an expert agent fleet from content sources.

This hook runs at bootstrap time (before the graph is built).  It:

1. Deletes any existing agents from the SQLite ``agent_configs`` table
   (idempotent — clean slate on every bootstrap).
2. Creates an **ephemeral Orchid instance** programmatically with two
   agents (a reader and a summariser) that collaborate via the full
   Orchid pipeline — supervisor routing, skills, tools, and the
   agentic tool-calling loop.
3. The ephemeral Orchid runs a single turn: the reader discovers and
   reads all documents from content sources, then the summariser
   analyses the results and produces JSON agent configurations.
4. The generated configs are persisted into ``agent_configs`` so that
   ``merge_from_db()`` (which runs immediately after this hook) picks
   them up.

The reader and summariser are configured **entirely in Python code** —
they do not appear in ``agents.yaml``.  The yaml only enables
``config_storage`` with an empty ``agents: {}`` dict.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Agent prompts (Python-coded, not in YAML)
# ═══════════════════════════════════════════════════════════════════

READER_PROMPT = """You are a document reader for a car dealership.
Your job is to read ALL available car specification documents and
compile a comprehensive report.

You have EXACTLY TWO tools available:
  list_content_files   — Lists all available files in the content directory.
  read_content_file    — Reads the full content of a specific file (pass the file path from list results).

You MUST use these tools — do NOT invent or call any other tool names.

RULES:
1. First, call list_content_files with no arguments to see what documents exist.
2. Then, for EVERY file returned, call read_content_file with that file's path.
3. Compile a structured report listing each document and its specifications.
3. Compile a structured report with one section per car brand/model,
   including ALL technical specifications (engine, fuel economy,
   dimensions, safety features, warranty).
4. Be thorough — don't skip any document or any specification.

Your output will be used by a summariser agent to create specialised
expert agents, so make sure every detail is captured."""

SUMMARISER_PROMPT = """You are a fleet architect for a car dealership.
Your job is to take a report of car specification documents and create
specialised expert agent configurations — one per car brand.

RULES:
1. Read the reader agent's document report in the conversation history.
2. For EACH distinct car brand (Toyota, Ford, Volkswagen, BMW, Audi,
   Honda, etc.), create ONE specialised agent configuration.
3. Each agent must have:
   - "name": a lowercase-kebab-case name (e.g. "toyota-expert")
   - "description": a one-line summary of the agent's expertise
   - "prompt": a SYSTEM PROMPT that contains:
     * The brand intro ("You are the Toyota vehicle expert...")
     * ALL technical specifications for that brand's vehicles
     * Instructions to answer accurately and cite the source document
     * Instructions to compare across brands when asked
     * A note that the specification data is authoritative
4. The output MUST be a VALID JSON array — nothing else.  No markdown
   fences, no extra prose, no trailing commas.

EXAMPLE OUTPUT:
[{"name": "toyota-expert", "description": "Specialist in Toyota Camry specifications", "prompt": "You are the Toyota vehicle expert with deep knowledge of the Camry lineup.\\n\\nKey Specifications:\\n- Engine: 2.5L 4-cylinder, 203 hp\\n- Fuel Economy: 28/39 MPG (city/hwy)\\n- Safety: Toyota Safety Sense 3.0\\n\\nAnswer questions accurately using only the specifications above. Cite the source document when providing technical details."}]"""


# ═══════════════════════════════════════════════════════════════════
# Startup hook entry point
# ═══════════════════════════════════════════════════════════════════

def _resolve_setting(settings: Any, env_name: str, default: str) -> str:
    """Read a setting value from a dict, Pydantic object, or env var.

    The ``settings`` parameter can be a ``dict`` (CLI), a Pydantic
    ``Settings`` instance (API), or ``None``.  Falls back to
    ``os.environ`` in all cases.
    """
    if isinstance(settings, dict):
        return settings.get(env_name, os.environ.get(env_name, default))
    if hasattr(settings, env_name.lower()):
        val = getattr(settings, env_name.lower(), None)
        return val if val else default
    return os.environ.get(env_name, default)


async def build_expert_fleet(
    *,
    reader: Any,
    settings: Any,
    runtime: Any,
    agents_config: Any = None,
    **kwargs: Any,
) -> None:
    """Startup hook — read content, analyse, create specialised agents.

    Called by ``_build_runtime()`` during bootstrap, BEFORE
    ``merge_from_db()`` runs, so agents created here are picked up
    automatically.
    """

    # ── 1. Gather content sources ──────────────────────────────
    content_sources: list[Any] = getattr(runtime, "content_sources", None) or []
    if not content_sources:
        logger.warning("[FleetBuilder] No content sources — skipping")
        return

    # Prefer the config_storage DSN from agents.yaml so the hook writes
    # to the same file that merge_from_db() reads from.  Fall back to
    # the env var / hardcoded default only when config_storage is absent.
    config_storage_dsn = (
        getattr(getattr(agents_config, "config_storage", None), "dsn", None)
        if agents_config is not None
        else None
    )
    db_dsn = os.path.expanduser(
        config_storage_dsn
        or _resolve_setting(settings, "CHAT_DB_DSN", "~/.orchid/car-dealer-fleet.db")
    )
    model = _resolve_setting(settings, "LITELLM_MODEL", "ollama/llama3.2")

    # ── 2. Delete existing agents (clean slate) ──────────────
    await _clear_existing_agents(db_dsn)

    # ── 3. Build programmatic OrchidAgentsConfig ─────────────────
    from orchid_ai.config.schema_agent import (
        OrchidAgentConfig,
        OrchidAgentsConfig,
        OrchidDefaultsConfig,
        ExecutionHints,
    )
    from orchid_ai.config.schema_llm import OrchidLLMConfig
    from orchid_ai.config.schema_rag import OrchidRAGDefaultsConfig
    from orchid_ai.config.schema_skills import (
        OrchidBuiltinToolConfig,
        BuiltinToolParameter,
        OrchidOrchestratorSkillConfig,
        OrchidOrchestratorSkillStepConfig,
    )

    config = OrchidAgentsConfig(
        version="1",
        defaults=OrchidDefaultsConfig(
            llm=OrchidLLMConfig(model=model, temperature=0.2),
            rag=OrchidRAGDefaultsConfig(enabled=False),
        ),
        tools={
            "list_content_files": OrchidBuiltinToolConfig(
                handler="orchid_ai.agents.content_tools.list_content_files",
                description="List available files in configured content directories. Call with no arguments to see all available documents.",
                parameters={
                    "path": BuiltinToolParameter(type="string", description="Subdirectory to list (leave empty for root)", required=False, default=""),
                    "recursive": BuiltinToolParameter(type="boolean", description="Include files in subdirectories (use True)", required=False, default="false"),
                    "limit": BuiltinToolParameter(type="integer", description="Maximum results", required=False, default="100"),
                },
            ),
            "read_content_file": OrchidBuiltinToolConfig(
                handler="orchid_ai.agents.content_tools.read_content_file",
                description="Read the full text content of a specific file. Pass the exact file path returned by list_content_files.",
                parameters={
                    "path": BuiltinToolParameter(type="string", description="File path (e.g. camry-2025-specs.md)", required=True, default=""),
                },
            ),
        },
        agents={
            "reader": OrchidAgentConfig(
                name="reader",
                description="Reads and retrieves all documents from content sources",
                prompt=READER_PROMPT,
                tools=["list_content_files", "read_content_file"],
                execution_hints=ExecutionHints(parallel_safe=True),
            ),
            "summariser": OrchidAgentConfig(
                name="summariser",
                description="Analyses documents and creates specialised expert agent configurations",
                prompt=SUMMARISER_PROMPT,
                execution_hints=ExecutionHints(parallel_safe=True),
            ),
        },
        skills={
            "build_expert_fleet": OrchidOrchestratorSkillConfig(
                description=(
                    "Read all car specification documents from content sources, "
                    "then analyse them and create one specialised expert agent "
                    "configuration per car brand."
                ),
                steps=[
                    OrchidOrchestratorSkillStepConfig(
                        agent="reader",
                        instruction=(
                            "List all available documents using list_content_files. "
                            "Then use read_content_file to read EVERY document. "
                            "Compile a thorough structured report with all technical "
                            "specifications per brand/model."
                        ),
                    ),
                    OrchidOrchestratorSkillStepConfig(
                        agent="summariser",
                        instruction=(
                            "Read the reader's document report from the conversation "
                            "history.  For EACH distinct car brand create a specialised "
                            "agent configuration.  Output a VALID JSON ARRAY of objects "
                            "with fields: name, description, prompt.  The prompt must "
                            "include ALL technical specifications for that brand.  "
                            "Output ONLY the JSON array — no markdown, no extra text."
                        ),
                    ),
                ],
            ),
        },
    )

    # ── 4. Build ephemeral OrchidRuntime ─────────────────────────
    from orchid_ai.runtime import OrchidRuntime

    ephemeral_runtime = OrchidRuntime(
        default_model=model,
        content_sources=content_sources,
    )

    # ── 5. Build and invoke the ephemeral graph ─────────────────
    from orchid_ai.graph.graph import build_graph
    from orchid_ai.core.state import OrchidAuthContext
    from langchain_core.messages import HumanMessage

    graph = build_graph(config=config, runtime=ephemeral_runtime)

    auth = OrchidAuthContext(
        access_token="fleet-builder",
        tenant_key="default",
        user_id="fleet-builder",
    )

    state: dict[str, Any] = {
        "messages": [
            HumanMessage(
                content=(
                    "Read ALL car specification documents from the content sources "
                    "and create ONE specialised expert agent configuration per car brand. "
                    "Each agent must include the full technical specifications for its brand."
                )
            ),
        ],
        "auth_context": auth,
        "chat_id": "fleet-builder",
    }

    logger.info("[FleetBuilder] Invoking ephemeral Orchid to build expert fleet...")
    result = await graph.ainvoke(state)

    # ── 6. Extract agent configs from the result ─────────────────
    fleet_configs = _extract_configs_from_result(result, model)

    if not fleet_configs:
        logger.warning("[FleetBuilder] No agent configs generated — fleet empty")
        return

    for cfg in fleet_configs:
        logger.info(
            "[FleetBuilder] Generated agent: %s — %s",
            cfg["name"],
            cfg.get("description", "(no description)"),
        )

    # ── 7. Persist to SQLite ─────────────────────────────────────
    await _persist_configs(db_dsn, fleet_configs)

    logger.info(
        "[FleetBuilder] Expert fleet created: %s",
        ", ".join(c["name"] for c in fleet_configs),
    )


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

async def _clear_existing_agents(db_dsn: str) -> None:
    import aiosqlite

    async with aiosqlite.connect(db_dsn) as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS agent_configs (
                name TEXT PRIMARY KEY, config TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        cursor = await conn.execute("SELECT COUNT(*) FROM agent_configs")
        row = await cursor.fetchone()
        count = row[0] if row else 0
        if count > 0:
            await conn.execute("DELETE FROM agent_configs")
            await conn.commit()
            logger.info("[FleetBuilder] Deleted %d existing agent(s)", count)


def _extract_configs_from_result(
    result: dict[str, Any],
    model: str,
) -> list[dict[str, Any]]:
    """Extract JSON agent configs from the ephemeral Orchid result.

    Looks through the conversation messages for the summariser's
    output which should contain a JSON array of agent configs.
    Falls back to a manual LLM call with litellm if extraction fails.
    """
    messages: list[Any] = result.get("messages", [])

    # Walk messages in reverse looking for the last AI message
    # containing a JSON array of agent configs
    for msg in reversed(messages):
        content = ""
        if hasattr(msg, "content"):
            content = str(msg.content)
        elif isinstance(msg, dict):
            content = str(msg.get("content", ""))

        if not content:
            continue

        configs = _try_parse_json(content)
        if configs:
            return configs

    # Fallback: Nothing found — log and return empty
    logger.warning("[FleetBuilder] Could not extract agent configs from ephemeral Orchid result")
    return []


def _try_parse_json(text: str) -> list[dict[str, Any]]:
    """Try to extract a JSON array of agent configs from text output.

    Handles:
    - Markdown code fences (`````json`)
    - Bare JSON array or object
    - Agent prefix wrappers (``[Summariser Agent]``)
    - Prose wrapping before/after the JSON
    """
    candidates: list[dict[str, Any]] = []

    def _collect(parsed: Any) -> bool:
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "name" in item and "prompt" in item:
                    candidates.append(item)
            return bool(candidates)
        if isinstance(parsed, dict) and "name" in parsed and "prompt" in parsed:
            candidates.append(parsed)
            return True
        return False

    # Try code blocks first
    in_block = False
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_block:
                try:
                    _collect(json.loads("\n".join(buf)))
                except json.JSONDecodeError:
                    pass
                if candidates:
                    return candidates
                buf, in_block = [], False
            else:
                in_block, buf = True, []
        elif in_block:
            buf.append(line)

    if candidates:
        return candidates

    # Try the whole text as JSON
    try:
        _collect(json.loads(text))
        if candidates:
            return candidates
    except json.JSONDecodeError:
        pass

    # Try to find the first JSON array in the text (handles agent prefixes
    # like ``[Summariser Agent]\n[...]`` and prose wrappers)
    start = text.find("[")
    while start != -1:
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "[":
                depth += 1
            elif text[end] == "]":
                depth -= 1
                if depth == 0:
                    try:
                        _collect(json.loads(text[start : end + 1]))
                        if candidates:
                            return candidates
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
        start = text.find("[", start + 1)

    # Try to find the first JSON object (single agent output)
    start = text.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        _collect(json.loads(text[start : end + 1]))
                        if candidates:
                            return candidates
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break
        start = text.find("{", start + 1)

    return candidates


async def _persist_configs(
    db_dsn: str,
    fleet_configs: list[dict[str, Any]],
) -> None:
    import aiosqlite

    async with aiosqlite.connect(db_dsn) as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS agent_configs (
                name TEXT PRIMARY KEY, config TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        await conn.commit()
        for cfg in fleet_configs:
            name = cfg["name"]
            agent_cfg = {
                "name": name,
                "description": cfg.get("description", ""),
                "prompt": cfg.get("prompt", ""),
                "rag": {"enabled": False},
                "tools": [],
            }
            config_json = json.dumps(agent_cfg)
            await conn.execute(
                """INSERT INTO agent_configs (name, config, created_at, updated_at)
                   VALUES (?, ?, datetime('now'), datetime('now'))
                   ON CONFLICT(name) DO UPDATE SET
                       config = excluded.config,
                       updated_at = excluded.updated_at""",
                (name, config_json),
            )
        await conn.commit()
    logger.info("[FleetBuilder] Persisted %d agent(s) to %s", len(fleet_configs), db_dsn)
