"""Configuration built entirely in Python — no orchid.yml, no agents.yaml.

This is the "purest" embedded form: everything (agents, prompts, tools,
RAG settings) is assembled as Python objects, and ``Orchid`` is
constructed with the low-level ``(config=..., runtime=...)`` signature.

When to use this shape:
  * Generating agents dynamically (one per tenant, per A/B bucket, per
    feature flag) without materialising YAML files on disk.
  * Embedding orchid inside a larger application where config lives in
    a database or a secrets manager.
  * Test fixtures — spin up a graph with exactly the agents the test
    needs.

Usage::

    cd orchid
    python -m examples.embedded-python.06_inline_config
"""

from __future__ import annotations

import asyncio

from orchid_ai import Orchid, OrchidRuntime
from orchid_ai.config.schema import (
    OrchidAgentConfig,
    OrchidAgentsConfig,
    OrchidDefaultsConfig,
    OrchidLLMConfig,
    OrchidRAGConfig,
    OrchidRAGDefaultsConfig,
)
from orchid_ai.config.tool_registry import ToolParameter, register_tool


# ── 1. In-process tool handler ──────────────────────────────────

def lookup_weather(*, city: str = "", **_kwargs) -> str:
    """Return canned weather for a city."""
    table = {
        "paris": "19°C, cloudy",
        "tokyo": "26°C, humid",
        "nyc": "21°C, partly sunny",
    }
    return table.get(city.lower(), f"No data for {city!r}")


# Registering before ``build_graph`` makes the tool available to any
# agent that lists it by name.  No dotted path needed — the handler is
# a plain Python callable captured from this script.
register_tool(
    "weather",
    lookup_weather,
    description="Current conditions for a city.",
    parameters={
        "city": ToolParameter(
            name="city",
            type="string",
            description="City name (paris, tokyo, nyc).",
            required=True,
        ),
    },
)


# ── 2. Agents config built as Python objects ───────────────────

def build_config() -> OrchidAgentsConfig:
    return OrchidAgentsConfig(
        version="1",
        defaults=OrchidDefaultsConfig(
            llm=OrchidLLMConfig(model="ollama/llama3.2", temperature=0.1),
            rag=OrchidRAGDefaultsConfig(enabled=False),
        ),
        agents={
            "weatherman": OrchidAgentConfig(
                description="Answers questions about today's weather.",
                prompt=(
                    "You are a concise weather assistant. "
                    "Use the `weather` tool for any city the user asks about."
                ),
                rag=OrchidRAGConfig(enabled=False),
                tools=["weather"],
            ),
        },
    )


# ── 3. Invoke ──────────────────────────────────────────────────

async def main() -> None:
    config = build_config()
    runtime = OrchidRuntime(default_model="ollama/llama3.2")

    async with Orchid(config=config, runtime=runtime) as client:
        result = await client.invoke(
            "What's the weather in Tokyo right now?",
            user_id="finn",
            tenant_id="demo",
            persist=False,
        )
        print(result.response)


if __name__ == "__main__":
    asyncio.run(main())
