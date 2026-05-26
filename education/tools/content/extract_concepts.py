from __future__ import annotations

from collections import Counter
import re

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "between",
    "could",
    "first",
    "from",
    "into",
    "many",
    "most",
    "other",
    "over",
    "should",
    "that",
    "their",
    "there",
    "these",
    "this",
    "those",
    "through",
    "under",
    "using",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
}


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _collect_headings(text: str) -> list[str]:
    headings: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if heading:
                headings.append(heading)
        elif line.isupper() and 2 <= len(line.split()) <= 8:
            headings.append(line.title())
    return headings


def _keyword_candidates(text: str, max_concepts: int) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", text.lower())
    filtered = [word for word in words if word not in _STOPWORDS]
    counts = Counter(filtered)
    return [word.replace("-", " ") for word, _ in counts.most_common(max_concepts * 2)]


def _find_description(name: str, sentences: list[str]) -> str:
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    for sentence in sentences:
        if pattern.search(sentence):
            return sentence
    return f"Key idea related to {name}."


class ExtractConceptsTool(OrchidTool):
    name = "extract_concepts"
    description = "Extract key concepts, headings, and repeated themes from source text"
    parameters_schema = {
        "type": "object",
        "properties": {
            "source_text": {
                "type": "string",
                "description": "Source material to analyze",
            },
            "max_concepts": {
                "type": "integer",
                "description": "Maximum number of concepts to return",
                "default": 15,
            },
        },
        "required": ["source_text"],
    }
    parallel_safe = True

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        source_text = str(tool_input.parameters["source_text"])
        max_concepts = max(1, int(tool_input.parameters.get("max_concepts", 15)))
        sentences = _split_sentences(source_text)
        headings = _collect_headings(source_text)
        keywords = _keyword_candidates(source_text, max_concepts)

        candidates = headings + keywords
        concepts = []
        seen: set[str] = set()
        for index, candidate in enumerate(candidates):
            normalized = re.sub(r"\s+", " ", candidate.strip().lower())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            importance = 5 if index < 3 else 4 if index < 8 else 3
            concepts.append(
                {
                    "name": candidate.strip().title(),
                    "description": _find_description(candidate, sentences),
                    "difficulty": "intermediate",
                    "importance": importance,
                }
            )
            if len(concepts) >= max_concepts:
                break

        return OrchidToolOutput(result=concepts)
