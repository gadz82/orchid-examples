from __future__ import annotations

from difflib import SequenceMatcher

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


class ValidateQuestionsTool(OrchidTool):
    name = "validate_questions"
    description = "Run structural validation checks on generated questions"
    parameters_schema = {
        "type": "object",
        "properties": {
            "questions": {"type": "array", "default": []},
            "source_text": {"type": "string", "default": ""},
        },
        "required": ["questions", "source_text"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        questions = list(tool_input.parameters.get("questions") or [])
        issues = []
        normalized_seen: list[tuple[int, str]] = []

        for index, question in enumerate(questions):
            prompt = str(question.get("question") or "").strip()
            if not prompt:
                issues.append({"question_index": index, "severity": "error", "message": "Question text is empty."})

            options = list(question.get("options") or [])
            if not options:
                issues.append({"question_index": index, "severity": "error", "message": "Options list is empty."})

            correct_index = question.get("correct_index")
            if not isinstance(correct_index, int) or correct_index < 0 or correct_index >= len(options or [None]):
                issues.append(
                    {
                        "question_index": index,
                        "severity": "error",
                        "message": "correct_index is missing or outside the options range.",
                    }
                )

            explanation = str(question.get("explanation") or "").strip()
            if len(explanation) < 10:
                issues.append(
                    {
                        "question_index": index,
                        "severity": "warning",
                        "message": "Explanation should be at least 10 characters.",
                    }
                )

            normalized = _normalize(prompt)
            for previous_index, previous_prompt in normalized_seen:
                if normalized and SequenceMatcher(a=normalized, b=previous_prompt).ratio() >= 0.92:
                    issues.append(
                        {
                            "question_index": index,
                            "severity": "warning",
                            "message": f"Question is very similar to question {previous_index}.",
                        }
                    )
                    break
            normalized_seen.append((index, normalized))

        return OrchidToolOutput(result={"valid": not any(issue["severity"] == "error" for issue in issues), "issues": issues})
