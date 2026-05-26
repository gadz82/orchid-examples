from __future__ import annotations

import pytest

from examples.education.tools.content.build_lesson import BuildLessonStructureTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_build_lesson_allocates_sections():
    tool = BuildLessonStructureTool()
    concepts = [{"name": "Photosynthesis"}, {"name": "Chlorophyll"}, {"name": "Glucose"}]

    output = await tool.invoke(
        OrchidToolInput(
            parameters={
                "concepts": concepts,
                "source_text": "# Photosynthesis\nPlants make food using light.",
                "duration_minutes": 40,
            }
        )
    )

    result = output.result
    assert result["title"] == "Photosynthesis"
    assert result["sections"]
    assert result["activities"]
    assert "summary_template" in result
    assert "assessment_template" in result
