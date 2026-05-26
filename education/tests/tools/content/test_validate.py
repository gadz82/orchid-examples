from __future__ import annotations

import pytest

from examples.education.tools.content.validate import ValidateQuestionsTool
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_validate_detects_structural_issues():
    tool = ValidateQuestionsTool()
    questions = [
        {"question": "", "options": [], "correct_index": 4, "explanation": "short"},
        {"question": "Repeat me", "options": ["A"], "correct_index": 0, "explanation": "This explanation is long enough."},
        {"question": "Repeat me", "options": ["A"], "correct_index": 0, "explanation": "This explanation is also long enough."},
    ]

    output = await tool.invoke(OrchidToolInput(parameters={"questions": questions, "source_text": "Sample"}))

    assert output.result["valid"] is False
    assert output.result["issues"]
