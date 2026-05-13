"""Minimal invocation — one request, one response.

Usage::

    cd orchid
    python -m examples.embedded-python.01_minimal
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from orchid_ai import Orchid


CONFIG = str(Path(__file__).with_name("orchid.yml"))


async def main() -> None:
    async with Orchid.from_config_path(CONFIG) as client:
        result = await client.invoke(
            "What's on the menu today?",
            user_id="alice",
            tenant_id="acme",
        )
        print("─── Response " + "─" * 48)
        print(result.response)
        print("─" * 60)
        print(f"chat_id       = {result.chat_id}")
        print(f"agents_used   = {result.agents_used}")


if __name__ == "__main__":
    asyncio.run(main())
