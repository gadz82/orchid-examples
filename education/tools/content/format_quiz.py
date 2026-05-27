from __future__ import annotations

import random
from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput


def _question_text(question: Any) -> str:
    if isinstance(question, dict):
        return str(question.get("question") or question.get("statement") or "Untitled question")
    return str(question)


class FormatMultipleChoiceTool(OrchidTool):
    name = "format_multiple_choice"
    description = "Format multiple-choice questions as Markdown with an answer key"
    parameters_schema = {
        "type": "object",
        "properties": {
            "questions": {"type": "array", "default": []},
            "shuffle_options": {"type": "boolean", "default": False},
        },
        "required": ["questions"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        questions = list(tool_input.parameters.get("questions") or [])
        shuffle_options = bool(tool_input.parameters.get("shuffle_options", False))
        lines = ["# Multiple Choice Quiz", ""]
        answer_key = ["## Answer Key", ""]

        for index, question in enumerate(questions, start=1):
            options = list(question.get("options") or [])
            correct_index = int(question.get("correct_index", 0))
            pairs = list(enumerate(options))
            if shuffle_options:
                random.Random(index).shuffle(pairs)
                correct_index = next(new_index for new_index, (old_index, _) in enumerate(pairs) if old_index == correct_index)
                options = [text for _, text in pairs]
            lines.append(f"{index}. {_question_text(question)}")
            for letter_index, option in enumerate(options):
                lines.append(f"   {chr(65 + letter_index)}. {option}")
            lines.append("")
            answer_key.append(f"{index}. {chr(65 + correct_index)}")

        return OrchidToolOutput(result="\n".join(lines + answer_key))


class FormatTrueFalseTool(OrchidTool):
    name = "format_true_false"
    description = "Format true-false questions as Markdown with a key"
    parameters_schema = {
        "type": "object",
        "properties": {"questions": {"type": "array", "default": []}},
        "required": ["questions"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        questions = list(tool_input.parameters.get("questions") or [])
        lines = ["# True / False Quiz", ""]
        answer_key = ["## Answer Key", ""]
        for index, question in enumerate(questions, start=1):
            lines.append(f"{index}. {_question_text(question)}")
            lines.append("   - [ ] True")
            lines.append("   - [ ] False")
            lines.append("")
            options = list(question.get("options") or ["True", "False"])
            correct_index = int(question.get("correct_index", 0))
            answer_key.append(f"{index}. {options[correct_index]}")
        return OrchidToolOutput(result="\n".join(lines + answer_key))


class FormatFillBlankTool(OrchidTool):
    name = "format_fill_blank"
    description = "Format fill-in-the-blank questions as Markdown with a word bank when useful"
    parameters_schema = {
        "type": "object",
        "properties": {"questions": {"type": "array", "default": []}},
        "required": ["questions"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        questions = list(tool_input.parameters.get("questions") or [])
        lines = ["# Fill in the Blank", ""]
        word_bank: list[str] = []
        for index, question in enumerate(questions, start=1):
            prompt = _question_text(question)
            if "__blank__" not in prompt:
                prompt = f"{prompt.rstrip('.')} __blank__."
            lines.append(f"{index}. {prompt}")
            answer = str(question.get("answer") or question.get("concept") or f"Answer {index}")
            word_bank.append(answer)
        lines.append("")
        if len(word_bank) > 2:
            lines.append("## Word Bank")
            lines.append(", ".join(word_bank))
            lines.append("")
        lines.append("## Answer Key")
        lines.extend(f"{index}. {answer}" for index, answer in enumerate(word_bank, start=1))
        return OrchidToolOutput(result="\n".join(lines))


class FormatMatchingTool(OrchidTool):
    name = "format_matching"
    description = "Format matching prompts into left and right columns"
    parameters_schema = {
        "type": "object",
        "properties": {"pairs": {"type": "array", "default": []}},
        "required": ["pairs"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        pairs = list(tool_input.parameters.get("pairs") or [])
        left_lines = []
        right_lines = []
        for index, pair in enumerate(pairs, start=1):
            if isinstance(pair, dict):
                prompt = str(pair.get("prompt") or pair.get("left") or pair.get("term") or f"Item {index}")
                answer = str(pair.get("answer") or pair.get("right") or pair.get("definition") or f"Match {index}")
            else:
                prompt = f"Item {index}"
                answer = str(pair)
            left_lines.append(f"{index}. {prompt}")
            right_lines.append(f"{chr(64 + index)}. {answer}")

        lines = ["# Matching Exercise", "", "## Column A", *left_lines, "", "## Column B", *right_lines]
        return OrchidToolOutput(result="\n".join(lines))
