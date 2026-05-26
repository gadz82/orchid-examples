from __future__ import annotations

from pathlib import Path

import pytest

from examples.education.tools.output.generate_txt import GenerateTXTTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_generate_txt(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = GenerateTXTTool()

    output = await tool.invoke(OrchidToolInput(parameters={"content": "hello", "filename": "quiz"}))

    path = Path(output.result["path"])
    assert path.suffix == ".txt"
    assert path.read_text(encoding="utf-8") == "hello"
    assert output.result["format"] == "txt"
