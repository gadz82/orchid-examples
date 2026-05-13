"""Human-in-the-loop (HITL) tool approval.

When an agent calls a tool flagged with ``requires_approval: true`` in
``agents.yaml``, the graph pauses via ``interrupt()`` and :meth:`invoke`
returns ``interrupted=True`` plus the list of pending approvals.  The
caller collects a decision (CLI prompt / UI button / policy engine /
scheduled approver) and calls :meth:`resume`.

Requires a checkpointer — enabled via the ``checkpointer:`` section in
``orchid.yml`` (this example uses SQLite by default).

Usage::

    cd orchid
    python -m examples.embedded-python.04_hitl
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
        result = await client.invoke(
            "Book a table for two tonight at 8pm.",
            chat_id=chat_id,
            user_id="dave",
            tenant_id="acme",
        )

        if not result.interrupted:
            print(f"Completed without approval: {result.response}")
            return

        print("Graph paused for tool approval:")
        for pending in result.approvals_needed:
            print(f"  • {pending.agent}.{pending.tool}({pending.args})")

        # Simulate an approval decision.  In production, hand this off to
        # your own approval mechanism (CLI prompt, UI, policy engine, ...).
        approved = True
        print(f"Decision: {'APPROVE' if approved else 'REJECT'}")

        final = await client.resume(chat_id, approved=approved)
        print(f"\nFinal response: {final.response}")


if __name__ == "__main__":
    asyncio.run(main())
