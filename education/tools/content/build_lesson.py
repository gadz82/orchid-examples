from __future__ import annotations

import math
from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput


def _extract_title(source_text: str) -> str:
    for line in source_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
        return stripped[:80]
    return "Lesson Plan"


def _concept_name(concept: Any) -> str:
    if isinstance(concept, dict):
        return str(concept.get("name") or "Concept")
    return str(concept)


def _bucket_concepts(concepts: list[Any], bucket_count: int) -> list[list[str]]:
    buckets: list[list[str]] = [[] for _ in range(bucket_count)]
    for index, concept in enumerate(concepts):
        buckets[index % bucket_count].append(_concept_name(concept))
    return buckets


class BuildLessonStructureTool(OrchidTool):
    name = "build_lesson_structure"
    description = "Build a timed lesson-plan scaffold from concepts and source text"
    parameters_schema = {
        "type": "object",
        "properties": {
            "concepts": {
                "type": "array",
                "description": "Concept records to organize into a lesson",
                "default": [],
            },
            "source_text": {
                "type": "string",
                "description": "Source material used to derive the lesson title and context",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Target lesson duration in minutes",
                "default": 30,
            },
        },
        "required": ["concepts", "source_text"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        concepts = list(tool_input.parameters.get("concepts") or [])
        source_text = str(tool_input.parameters["source_text"])
        duration_minutes = max(10, int(tool_input.parameters.get("duration_minutes", 30)))

        intro_duration = max(1, round(duration_minutes * 0.10))
        section_duration_total = max(1, round(duration_minutes * 0.60))
        activity_duration_total = max(1, round(duration_minutes * 0.20))
        assessment_duration = max(1, duration_minutes - intro_duration - section_duration_total - activity_duration_total)

        section_count = max(1, min(len(concepts) or 1, max(1, duration_minutes // 10)))
        concept_buckets = _bucket_concepts(concepts or ["Core Idea"], section_count)
        section_duration = max(1, math.floor(section_duration_total / section_count))

        sections = []
        for index, bucket in enumerate(concept_buckets, start=1):
            focus = ", ".join(bucket) if bucket else "Core Idea"
            sections.append(
                {
                    "title": f"Section {index}: {focus}",
                    "duration": section_duration,
                    "content_template": (
                        f"Introduce {focus}. Explain the central idea, provide one grounded example, "
                        "and add one comprehension check."
                    ),
                }
            )

        activities = [
            {
                "name": "Warm-up reflection",
                "type": "individual",
                "duration": max(1, intro_duration),
            },
            {
                "name": "Guided practice",
                "type": "collaborative",
                "duration": max(1, activity_duration_total),
            },
        ]

        concept_names = [_concept_name(concept) for concept in concepts] or ["the main topic"]
        objectives = [f"Explain {name.lower()} in your own words." for name in concept_names[:3]]

        result = {
            "title": _extract_title(source_text),
            "objectives": objectives,
            "sections": sections,
            "activities": activities,
            "summary_template": (
                f"Close the lesson by summarizing {', '.join(concept_names[:3])} and connecting them to the main objective."
            ),
            "assessment_template": (
                f"Use a {assessment_duration}-minute exit check that asks learners to apply {concept_names[0]}."
            ),
        }
        return OrchidToolOutput(result=result)
