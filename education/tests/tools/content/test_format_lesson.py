from __future__ import annotations

import pytest

from examples.education.tools.content.format_lesson import DefineLearningObjectivesTool, FormatLessonSectionTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_define_learning_objectives():
    tool = DefineLearningObjectivesTool()
    output = await tool.invoke(
        OrchidToolInput(parameters={"concepts": [{"name": "Photosynthesis", "difficulty": "beginner"}]})
    )
    assert output.result
    assert "Remember" in output.result[0]


@pytest.mark.asyncio
async def test_format_lesson_section():
    tool = FormatLessonSectionTool()
    output = await tool.invoke(
        OrchidToolInput(parameters={"section": {"title": "Overview", "duration": 8, "content_template": "Explain the process."}})
    )
    assert "## Overview" in output.result
    assert "_Timing: 8 minutes_" in output.result
