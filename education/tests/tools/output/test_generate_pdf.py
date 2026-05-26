from __future__ import annotations

from pathlib import Path

import pytest

from examples.education.tools.output.generate_pdf import GeneratePDFTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_generate_pdf(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = GeneratePDFTool()

    output = await tool.invoke(
        OrchidToolInput(parameters={"content": "# Heading\n\nBody text", "filename": "lesson-pack", "title": "Lesson"})
    )

    path = Path(output.result["path"])
    assert path.suffix == ".pdf"
    assert path.read_bytes().startswith(b"%PDF")
    assert output.result["format"] == "pdf"
