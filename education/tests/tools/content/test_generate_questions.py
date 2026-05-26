from __future__ import annotations

import pytest

from examples.education.tools.content.generate_questions import GenerateQuestionsTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_generate_questions_allocates_round_robin():
    tool = GenerateQuestionsTool()
    concepts = [{"name": "Photosynthesis"}, {"name": "Chlorophyll"}]

    output = await tool.invoke(
        OrchidToolInput(parameters={"concepts": concepts, "count": 4, "types": ["multiple_choice", "true_false"]})
    )

    assert len(output.result) == 4
    assert output.result[0]["concept"] == "Photosynthesis"
    assert output.result[1]["concept"] == "Chlorophyll"
    assert output.result[0]["type"] == "multiple_choice"
    assert output.result[1]["type"] == "true_false"
