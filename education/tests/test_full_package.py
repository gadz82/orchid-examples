from __future__ import annotations

from pathlib import Path

import pytest


def _build_lesson_markdown(title: str, objectives: list[str], sections: list[str], summary: str, assessment: str) -> str:
    lines = [f"# {title}", "", "## Learning Objectives", ""]
    lines.extend(f"- {objective}" for objective in objectives)
    lines.append("")
    lines.extend(sections)
    lines.extend(["", "## Summary", "", summary, "", "## Assessment", "", assessment])
    return "\n".join(lines)


@pytest.mark.asyncio
async def test_full_package_flow(education_config, run_tool, sample_text: str, secondary_text: str) -> None:
    assert "generate_full_package" in education_config.skills
    assert education_config.agents["format-exporter"].rag.enabled is False

    source_text = f"{sample_text}\n\n{secondary_text}"
    concepts = (
        await run_tool("extract_concepts", {"source_text": source_text, "max_concepts": 8})
    ).result
    questions = (
        await run_tool(
            "generate_questions",
            {
                "concepts": concepts,
                "count": 6,
                "types": ["multiple_choice"],
                "difficulty": "mixed",
            },
        )
    ).result
    validation = (
        await run_tool("validate_questions", {"questions": questions, "source_text": source_text})
    ).result
    quiz_markdown = (await run_tool("format_multiple_choice", {"questions": questions})).result

    lesson = (
        await run_tool(
            "build_lesson_structure",
            {
                "concepts": concepts,
                "source_text": source_text,
                "duration_minutes": 35,
            },
        )
    ).result
    objectives = (await run_tool("define_learning_objectives", {"concepts": concepts})).result
    formatted_sections = [
        (
            await run_tool("format_lesson_section", {"section": section})
        ).result
        for section in lesson["sections"]
    ]
    lesson_markdown = _build_lesson_markdown(
        lesson["title"],
        objectives,
        formatted_sections,
        lesson["summary_template"],
        lesson["assessment_template"],
    )

    slides = [
        {"title": section["title"], "content": section["content_template"]}
        for section in lesson["sections"]
    ]
    exports = [
        await run_tool("generate_pdf", {"content": quiz_markdown, "filename": "quiz/review-quiz", "title": "Review Quiz"}),
        await run_tool("generate_markdown", {"content": quiz_markdown, "filename": "quiz/review-quiz"}),
        await run_tool(
            "generate_docx",
            {
                "content": lesson_markdown,
                "filename": "lesson/lesson-plan",
                "title": lesson["title"],
                "sections": lesson["sections"],
            },
        ),
        await run_tool("generate_txt", {"content": lesson_markdown, "filename": "lesson/lesson-plan"}),
        await run_tool("generate_pptx", {"slides": slides, "filename": "slides/lesson-deck", "title": lesson["title"]}),
    ]

    assert validation["valid"] is True
    assert "## Learning Objectives" in lesson_markdown
    for output in exports:
        exported_path = Path(output.result["path"])
        assert exported_path.exists()
        assert "education-demo" in exported_path.parts
