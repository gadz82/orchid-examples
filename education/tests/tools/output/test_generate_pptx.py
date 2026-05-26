from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from examples.education.tools.output.generate_pptx import GeneratePPTXTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_generate_pptx(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = GeneratePPTXTool()

    output = await tool.invoke(
        OrchidToolInput(
            parameters={
                "slides": [
                    {"title": "Topic A", "content": "Point 1\nPoint 2"},
                    {"title": "Topic B", "content": "Point 3"},
                ],
                "filename": "lesson-slides",
                "title": "Course Deck",
            }
        )
    )

    path = Path(output.result["path"])
    assert path.suffix == ".pptx"
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
    assert "[Content_Types].xml" in names
    assert "ppt/presentation.xml" in names
    assert "ppt/slides/slide1.xml" in names
    assert "ppt/slides/slide2.xml" in names
    assert "ppt/slides/slide3.xml" in names
    assert output.result["format"] == "pptx"
