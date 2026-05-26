from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_DEFAULT_TYPES = ["multiple_choice"]


def _concept_name(concept: Any) -> str:
    if isinstance(concept, dict):
        return str(concept.get("name") or concept.get("concept") or "Concept")
    return str(concept)


class GenerateQuestionsTool(OrchidTool):
    name = "generate_questions"
    description = "Allocate question scaffolds across concepts and question types"
    parameters_schema = {
        "type": "object",
        "properties": {
            "concepts": {
                "type": "array",
                "description": "Concept records to cover",
                "default": [],
            },
            "count": {
                "type": "integer",
                "description": "Number of question scaffolds to produce",
            },
            "types": {
                "type": "array",
                "description": "Question types to rotate through",
                "default": _DEFAULT_TYPES,
            },
            "difficulty": {
                "type": "string",
                "description": "Requested difficulty level or 'mixed'",
                "default": "mixed",
            },
        },
        "required": ["concepts", "count"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        concepts = list(tool_input.parameters.get("concepts") or [])
        count = max(0, int(tool_input.parameters.get("count", 0)))
        requested_difficulty = str(tool_input.parameters.get("difficulty", "mixed"))
        question_types = [str(item) for item in (tool_input.parameters.get("types") or _DEFAULT_TYPES)] or _DEFAULT_TYPES

        if not concepts or count == 0:
            return OrchidToolOutput(result=[])

        questions = []
        for index in range(count):
            concept = concepts[index % len(concepts)]
            concept_name = _concept_name(concept)
            question_type = question_types[index % len(question_types)]
            concept_difficulty = concept.get("difficulty") if isinstance(concept, dict) else None
            difficulty = concept_difficulty if requested_difficulty == "mixed" and concept_difficulty else requested_difficulty
            options = [
                f"Placeholder option A for {concept_name}",
                f"Placeholder option B for {concept_name}",
                f"Placeholder option C for {concept_name}",
                f"Placeholder option D for {concept_name}",
            ]
            if question_type == "true_false":
                options = ["True", "False"]

            questions.append(
                {
                    "question": f"Draft a {question_type.replace('_', ' ')} question about {concept_name}.",
                    "options": options,
                    "correct_index": 0,
                    "explanation": f"Explain the reasoning for the correct answer about {concept_name}.",
                    "type": question_type,
                    "concept": concept_name,
                    "difficulty": difficulty or "intermediate",
                }
            )

        return OrchidToolOutput(result=questions)
