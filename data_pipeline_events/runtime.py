"""Small composition helpers for the event-driven pipeline example."""

from __future__ import annotations

from typing import Any

from orchid_ai.orchid.orchid import Orchid


class FacadePipelineRunner:
    """Adapt the Orchid facade to the events pipeline-runner protocol.

    Bloom runs use chat interpretation, matching orchid-api and orchid-cli;
    forwarding ``bloom`` straight to the facade would silently select direct
    mode and change the summary the chat receives.
    """

    def __init__(self, orchid: Orchid) -> None:
        self._orchid = orchid
        self.last_mode: str | None = None

    async def run(
        self,
        name: str,
        pipeline_input: dict[str, Any],
        *,
        auth: Any,
        mode: str,
        correlation_id: str | None,
        chat_id: str | None,
        include_graph: bool,
    ) -> Any:
        facade_mode = "chat" if mode in ("bloom", "chat") else "direct"
        self.last_mode = facade_mode
        return await self._orchid.run_pipeline(
            name,
            pipeline_input,
            auth=auth,
            mode=facade_mode,
            correlation_id=correlation_id,
            chat_id=chat_id,
            include_graph=include_graph,
        )
