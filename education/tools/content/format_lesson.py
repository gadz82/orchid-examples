from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_BLOOM_VERBS = {
    "beginner": ("Remember", "Understand"),
    "intermediate": ("Apply", "Analyze"),
    "advanced": ("Evaluate", "Create"),
}


def _concept_name(concept: Any) -> str:
    if isinstance(concept, dict):
        return str(concept.get("name") or "Concept")
    return str(concept)


class DefineLearningObjectivesTool(OrchidTool):
    name = "define_learning_objectives"
    description = "Create learning objectives aligned to Bloom's taxonomy"
    parameters_schema = {
        "type": "object",
        "properties": {"concepts": {"type": "array", "default": []}},
        "required": ["concepts"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        concepts = list(tool_input.parameters.get("concepts") or [])
        objectives = []
        for concept in concepts:
            difficulty = str(concept.get("difficulty", "intermediate")) if isinstance(concept, dict) else "intermediate"
            verbs = _BLOOM_VERBS.get(difficulty, _BLOOM_VERBS["intermediate"])
            name = _concept_name(concept).lower()
            objectives.append(f"{verbs[0]} and {verbs[1]} {name} using evidence from the lesson.")
        return OrchidToolOutput(result=objectives)


class FormatLessonSectionTool(OrchidTool):
    name = "format_lesson_section"
    description = "Format one lesson section as Markdown with heading, timing, and body"
    parameters_schema = {
        "type": "object",
        "properties": {"section": {"type": "object", "default": {}}},
        "required": ["section"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        section = dict(tool_input.parameters.get("section") or {})
        title = str(section.get("title") or "Lesson Section")
        duration = section.get("duration")
        content = section.get("content") or section.get("content_template") or section.get("summary") or ""
        lines = [f"## {title}"]
        if duration not in (None, ""):
            lines.append(f"_Timing: {duration} minutes_")
        lines.append("")
        if isinstance(content, list):
            lines.extend(f"- {item}" for item in content)
        else:
            lines.append(str(content))
        return OrchidToolOutput(result="\n".join(lines))
