from __future__ import annotations

import pytest

from examples.education.tools.content.format_quiz import (
    FormatFillBlankTool,
    FormatMatchingTool,
    FormatMultipleChoiceTool,
    FormatTrueFalseTool,
)
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_format_multiple_choice_markdown():
    tool = FormatMultipleChoiceTool()
    output = await tool.invoke(
        OrchidToolInput(
            parameters={"questions": [{"question": "What is light?", "options": ["A", "B"], "correct_index": 1}]}
        )
    )
    assert "# Multiple Choice Quiz" in output.result
    assert "## Answer Key" in output.result


@pytest.mark.asyncio
async def test_format_true_false_markdown():
    tool = FormatTrueFalseTool()
    output = await tool.invoke(
        OrchidToolInput(parameters={"questions": [{"question": "Plants need light.", "options": ["True", "False"], "correct_index": 0}]})
    )
    assert "# True / False Quiz" in output.result
    assert "- [ ] True" in output.result


@pytest.mark.asyncio
async def test_format_fill_blank_markdown():
    tool = FormatFillBlankTool()
    output = await tool.invoke(OrchidToolInput(parameters={"questions": [{"question": "Plants create sugar", "answer": "glucose"}]}))
    assert "# Fill in the Blank" in output.result
    assert "__blank__" in output.result


@pytest.mark.asyncio
async def test_format_matching_markdown():
    tool = FormatMatchingTool()
    output = await tool.invoke(OrchidToolInput(parameters={"pairs": [{"prompt": "Leaf", "answer": "Photosynthesis site"}]}))
    assert "# Matching Exercise" in output.result
    assert "## Column A" in output.result
