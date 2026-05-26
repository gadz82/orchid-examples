from __future__ import annotations

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

from .write_file import _ensure_extension, _write_content


class GenerateTXTTool(OrchidTool):
    name = "generate_txt"
    description = "Generate a plain-text file from text content"
    parameters_schema = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Plain-text content to write",
            },
            "filename": {
                "type": "string",
                "description": "Output filename without extension",
            },
        },
        "required": ["content", "filename"],
    }
    parallel_safe = False

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        parameters = tool_input.parameters
        filepath = str(_ensure_extension(str(parameters["filename"]), ".txt"))
        path, size, download_url = _write_content(
            str(parameters["content"]),
            filepath=filepath,
            mode="text",
            context=tool_input.context,
            content_sources=tool_input.content_sources,
            auth_context=tool_input.auth_context,
        )
        return OrchidToolOutput(
            result={"path": str(path), "size_bytes": size, "format": "txt", "download_url": download_url},
            metadata={"mime": "text/plain"},
        )
