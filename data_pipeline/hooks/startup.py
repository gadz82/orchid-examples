"""Attach a process-local signal sink so the example's emit job runs offline.

The API replaces this emitter with the real events dispatcher once its
Pollen/Bloom layer boots. A direct CLI run has no events subsystem, so the
sink keeps the emit job observable without requiring SQLite, a queue or a
network service.
"""

from __future__ import annotations

import uuid
from typing import Any

from orchid_ai.core.events.signal import SignalIngestResult


class LocalSignalSink:
    """Collect emitted envelopes in memory for a single process."""

    def __init__(self) -> None:
        self.signals: list[Any] = []

    async def emit(self, envelope: Any) -> SignalIngestResult:
        self.signals.append(envelope)
        return SignalIngestResult(signal_id=uuid.uuid4(), queue_msg_id=None, deduplicated=False)


async def attach_local_signal_sink(
    reader: Any,
    settings: Any,
    runtime: Any,
    agents_config: Any = None,
    **_: Any,
) -> None:
    """Install :class:`LocalSignalSink` on the runtime when none is configured."""
    if getattr(runtime, "signal_emitter", None) is None:
        runtime.signal_emitter = LocalSignalSink()
