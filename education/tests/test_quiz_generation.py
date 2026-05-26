from __future__ import annotations

import pytest


async def _generate_quiz(run_tool, source_text: str, *, count: int = 4) -> dict:
    concepts_output = await run_tool(
        "extract_concepts",
        {"source_text": source_text, "max_concepts": 6},
    )
    questions_output = await run_tool(
        "generate_questions",
        {
            "concepts": concepts_output.result,
            "count": count,
            "types": ["multiple_choice"],
            "difficulty": "mixed",
        },
    )
    validation_output = await run_tool(
        "validate_questions",
        {"questions": questions_output.result, "source_text": source_text},
    )
    markdown_output = await run_tool(
        "format_multiple_choice",
        {"questions": questions_output.result},
    )
    return {
        "concepts": concepts_output.result,
        "questions": questions_output.result,
        "validation": validation_output.result,
        "markdown": markdown_output.result,
    }


@pytest.mark.asyncio
async def test_generate_quiz_from_text(education_config, run_tool, sample_text: str) -> None:
    assert "generate_quiz" in education_config.skills
    assert education_config.skills["generate_quiz"].steps[0].agent == "content-analyzer"

    result = await _generate_quiz(run_tool, sample_text)

    assert len(result["concepts"]) >= 3
    assert len(result["questions"]) == 4
    assert result["validation"]["valid"] is True
    assert "# Multiple Choice Quiz" in result["markdown"]
    assert "## Answer Key" in result["markdown"]


@pytest.mark.asyncio
async def test_missing_source_rejected(run_tool) -> None:
    with pytest.raises(KeyError, match="source_text"):
        await run_tool("extract_concepts", {})


@pytest.mark.asyncio
async def test_quiz_has_answers(run_tool, sample_text: str) -> None:
    result = await _generate_quiz(run_tool, sample_text, count=5)

    assert all(isinstance(question["correct_index"], int) for question in result["questions"])
    assert all(question["explanation"] for question in result["questions"])
    assert all(len(question["options"]) >= 2 for question in result["questions"])
