from __future__ import annotations

import pytest

from examples.education.tools.content.extract_concepts import ExtractConceptsTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_extract_concepts_returns_shaped_results():
    tool = ExtractConceptsTool()
    text = """# Photosynthesis\nPhotosynthesis converts light energy into chemical energy.\nPlants use chlorophyll to absorb sunlight."""

    output = await tool.invoke(OrchidToolInput(parameters={"source_text": text, "max_concepts": 4}))

    assert output.result
    first = output.result[0]
    assert {"name", "description", "difficulty", "importance"} <= set(first)
