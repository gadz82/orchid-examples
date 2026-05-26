from __future__ import annotations

from pathlib import Path

import pytest

from examples.education.tools.output.generate_markdown import GenerateMarkdownTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_generate_markdown(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = GenerateMarkdownTool()

    output = await tool.invoke(OrchidToolInput(parameters={"content": "# Heading", "filename": "lesson"}))

    path = Path(output.result["path"])
    assert path.suffix == ".md"
    assert path.read_text(encoding="utf-8") == "# Heading"
    assert output.result["format"] == "md"
