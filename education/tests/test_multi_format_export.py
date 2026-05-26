from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_multi_format_export(run_tool, sample_text: str) -> None:
    markdown = "# Photosynthesis Review\n\n- Light reactions\n- Calvin cycle\n"
    slides = [
        {"title": "Photosynthesis Review", "content": "Light reactions\nCalvin cycle"},
        {"title": "Why It Matters", "content": "Plants store chemical energy as glucose."},
    ]

    outputs = [
        await run_tool("generate_pdf", {"content": markdown, "filename": "exports/review", "title": "Photosynthesis Review"}),
        await run_tool("generate_docx", {"content": markdown, "filename": "exports/review", "title": "Photosynthesis Review"}),
        await run_tool("generate_pptx", {"slides": slides, "filename": "exports/review", "title": "Photosynthesis Review"}),
        await run_tool("generate_markdown", {"content": markdown, "filename": "exports/review"}),
        await run_tool("generate_txt", {"content": sample_text, "filename": "exports/review"}),
    ]

    exported_paths = [Path(output.result["path"]) for output in outputs]
    assert {path.suffix for path in exported_paths} == {".pdf", ".docx", ".pptx", ".md", ".txt"}
    assert all(path.exists() for path in exported_paths)
    assert all("education-demo" in path.parts for path in exported_paths)
