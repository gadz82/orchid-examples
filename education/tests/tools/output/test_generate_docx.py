from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from examples.education.tools.output.generate_docx import GenerateDOCXTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_generate_docx(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = GenerateDOCXTool()

    output = await tool.invoke(
        OrchidToolInput(
            parameters={
                "content": "# Overview\n- Item one",
                "filename": "lesson-doc",
                "title": "Overview",
                "sections": [{"title": "Section A", "content": "Body"}],
            }
        )
    )

    path = Path(output.result["path"])
    assert path.suffix == ".docx"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    assert "[Content_Types].xml" in names
    assert "word/document.xml" in names
    assert output.result["format"] == "docx"
