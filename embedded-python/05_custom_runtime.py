"""Lower-level usage: build your own OrchidRuntime and inject it.

Use this shape when you need to override defaults the ``from_config_path``
factory hides — e.g. inject a pre-configured ``ChatOpenAI`` instance with
custom retry/fallback rules, a specific Qdrant client, or a custom MCP
client factory.

Usage::

    cd orchid
    python -m examples.embedded-python.05_custom_runtime
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from orchid_ai import Orchid, OrchidRuntime, load_config


CONFIG = str(Path(__file__).parent.parent / "restaurant/config/agents.yaml")


async def main() -> None:
    config = load_config(CONFIG)

    # Minimal runtime — no RAG reader, no checkpointer, uses default
    # chat model built from ``default_model``.  Extend as needed.
    runtime = OrchidRuntime(default_model="gemini/gemini-flash-latest")

    # Low-level constructor: no chat_repo / no mcp_token_store → the
    # client does not persist messages and expects the caller to pass
    # ``history`` explicitly when running multi-turn.
    client = Orchid(config=config, runtime=runtime)
    try:
        result = await client.invoke(
            "What are tonight's specials?",
            user_id="erin",
            tenant_id="acme",
            persist=False,
        )
        print(result.response)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
