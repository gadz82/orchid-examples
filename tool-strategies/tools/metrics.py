"""Read-only metric tools used by the ``parallel_searcher`` agent.

Three sibling tools that each return a single scalar; declared
``parallel_safe`` so the agentic loop's Phase A parallel dispatch can
gather them in a single ``asyncio.gather`` call within one round.
"""

from __future__ import annotations

import asyncio
from typing import Any


async def metric_a(**_: Any) -> dict[str, Any]:
    """Pretend to read metric A from a fast read replica."""
    await asyncio.sleep(0.05)
    return {"metric": "a", "value": 0.42}


async def metric_b(**_: Any) -> dict[str, Any]:
    """Pretend to read metric B from a fast read replica."""
    await asyncio.sleep(0.05)
    return {"metric": "b", "value": 12.0}


async def metric_c(**_: Any) -> dict[str, Any]:
    """Pretend to read metric C from a fast read replica."""
    await asyncio.sleep(0.05)
    return {"metric": "c", "value": 3.14}
