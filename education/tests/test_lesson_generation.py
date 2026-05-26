from __future__ import annotations

import pytest


async def _generate_lesson(run_tool, source_text: str, *, duration_minutes: int = 30) -> dict:
    concepts_output = await run_tool(
        "extract_concepts",
        {"source_text": source_text, "max_concepts": 5},
    )
    lesson_output = await run_tool(
        "build_lesson_structure",
        {
            "concepts": concepts_output.result,
            "source_text": source_text,
            "duration_minutes": duration_minutes,
        },
    )
    objectives_output = await run_tool(
        "define_learning_objectives",
        {"concepts": concepts_output.result},
    )
    first_section_output = await run_tool(
        "format_lesson_section",
        {"section": lesson_output.result["sections"][0]},
    )
    return {
        "concepts": concepts_output.result,
        "lesson": lesson_output.result,
        "objectives": objectives_output.result,
        "formatted_section": first_section_output.result,
    }


@pytest.mark.asyncio
async def test_generate_lesson_from_text(education_config, run_tool, sample_text: str) -> None:
    assert "generate_lesson" in education_config.skills
    assert education_config.agents["lesson-builder"].rag.namespace == "education"

    result = await _generate_lesson(run_tool, sample_text)

    assert result["lesson"]["title"] == "Photosynthesis"
    assert result["lesson"]["sections"]
    assert result["objectives"]
    assert result["formatted_section"].startswith("## Section 1")


@pytest.mark.asyncio
async def test_lesson_duration_allocation(run_tool, sample_text: str) -> None:
    result = await _generate_lesson(run_tool, sample_text, duration_minutes=40)
    sections = result["lesson"]["sections"]

    assert len(sections) == 4
    assert all(section["duration"] > 0 for section in sections)
    assert result["lesson"]["activities"][0]["duration"] > 0
