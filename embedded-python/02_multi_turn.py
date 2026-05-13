"""Multi-turn conversation reusing a chat_id.

Because ``persist=True`` is the default and chat_repo is auto-configured
from orchid.yml, subsequent calls with the same ``chat_id`` pick up the
prior history from SQLite automatically.

Usage::

    cd orchid
    python -m examples.embedded-python.02_multi_turn
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from orchid_ai import Orchid


CONFIG = str(Path(__file__).with_name("orchid.yml"))


async def main() -> None:
    chat_id = str(uuid.uuid4())

    async with Orchid.from_config_path(CONFIG) as client:
        turn_1 = await client.invoke(
            "Do you have any vegetarian pasta?",
            chat_id=chat_id,
            user_id="bob",
            tenant_id="acme",
        )
        print(f"Turn 1: {turn_1.response}\n")

        turn_2 = await client.invoke(
            "Is that gluten-free?",
            chat_id=chat_id,              # same chat — history auto-loaded
            user_id="bob",
            tenant_id="acme",
        )
        print(f"Turn 2: {turn_2.response}\n")

        turn_3 = await client.invoke(
            "Thanks — what's the price?",
            chat_id=chat_id,
            user_id="bob",
            tenant_id="acme",
        )
        print(f"Turn 3: {turn_3.response}\n")


if __name__ == "__main__":
    asyncio.run(main())
