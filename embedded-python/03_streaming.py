"""Token-level streaming.

LangGraph's ``astream`` exposes multiple modes; here we use ``"messages"``
to receive individual LLM tokens as they are produced.

Usage::

    cd orchid
    python -m examples.embedded-python.03_streaming
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from langchain_core.messages import AIMessageChunk

from orchid_ai import Orchid


CONFIG = str(Path(__file__).with_name("orchid.yml"))


async def main() -> None:
    async with Orchid.from_config_path(CONFIG) as client:
        print("Assistant: ", end="", flush=True)

        async for mode, chunk in client.stream(
            "Describe the chef's special in two sentences.",
            user_id="carol",
            tenant_id="acme",
            stream_mode="messages",
        ):
            if mode != "messages":
                continue
            token, _meta = chunk
            if isinstance(token, AIMessageChunk) and token.content:
                print(token.content, end="", flush=True)

        print()  # trailing newline


if __name__ == "__main__":
    asyncio.run(main())
