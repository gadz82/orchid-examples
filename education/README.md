# Education Studio

Four-agent teaching workflow that turns uploaded course material into quizzes, lesson plans, and multi-format export packages.

## Architecture

| Agent | Role | Tools |
|-------|------|-------|
| **content-analyzer** | Extracts concepts, headings, and themes from source material | `extract_concepts` |
| **quiz-generator** | Generates grounded questions with answer keys | `generate_questions`, `validate_questions` |
| **lesson-builder** | Builds paced lesson plans with Bloom-aligned objectives | `build_lesson_structure`, `define_learning_objectives`, `format_lesson_section` |
| **format-exporter** | Exports artifacts as PDF, DOCX, PPTX, Markdown, or plain text | 9 format/export tools |

## Framework features highlighted

- **16 `OrchidTool` subclasses** with declarative `parameters_schema` and `parallel_safe` — tools are dotted-import-resolved classes, not plain functions
- **Mini-agents (Pollen)** — `quiz-generator` fans out into parallel sub-tasks when source has multiple sections; custom decompose/aggregate prompts
- **3 cross-agent skills** — `generate_quiz`, `generate_lesson`, `generate_full_package` chain 3–4 agents sequentially
- **RAG namespace scoping** — 3 distinct namespaces (`education-source`, `education`, `education-exports`) isolate content layers
- **Event-driven scheduling** — APScheduler cron fires `weekly-quiz` every Monday at 08:00 as a service account with `visibility: tenant`
- **Chat-bound events** — `respect_chat_binding: true` attaches event output to the originating conversation
- **Custom `OrchidIdentityResolver`** — implements `resolve_service_account()` and `mint_for_user()`
- **Multi-format export** — direct file output via PDF (reportlab), DOCX (python-docx), PPTX (python-pptx), Markdown, and plain text

## Prerequisites

- Python 3.11+
- Google Gemini API key — get one at https://aistudio.google.com/apikey
- Qdrant running at `http://qdrant:6333` (or adjust `qdrant_url` in `orchid.yml`)

## Quick start

```bash
export GEMINI_API_KEY="your-key-here"

# Install
pip install -e ./orchid -e ./orchid-api
pip install reportlab python-pptx

# Launch
ORCHID_CONFIG=examples/education/orchid.yml \
  GEMINI_API_KEY=$GEMINI_API_KEY \
  uvicorn orchid_api.main:app --port 8000 --reload
```

Or use the website launcher script:

```bash
./orchid-website/scripts/start-education.sh
```

## Usage

1. Upload a PDF or document via the chat — the framework auto-chunks and indexes it under the `education-uploads` namespace
2. Ask the assistant to generate a quiz, lesson plan, or full teaching package
3. Request a specific export format (PDF, DOCX, PPTX, Markdown, or plain text)

Cross-agent skills are invoked by name:
- "Generate a quiz from the uploaded material"
- "Build a lesson plan on this topic"
- "Create a full teaching package with quiz, lesson, and slides"

## Tests

```bash
pip install -e ./orchid -e ./orchid-api pytest
pytest examples/education/tests/ -x -v
```

## Project structure

```
examples/education/
├── orchid.yml              # Runtime config (LLM, RAG, storage)
├── agents.yaml             # Agent definitions, tools, skills, events
├── identity.py             # Custom OrchidIdentityResolver
├── requirements.txt        # Extra Python deps (reportlab, python-pptx)
├── README.md
├── tools/
│   ├── content/            # Content analysis tools
│   │   ├── extract_concepts.py
│   │   ├── generate_questions.py
│   │   ├── validate.py
│   │   ├── build_lesson.py
│   │   ├── format_lesson.py
│   │   └── format_quiz.py
│   └── output/             # Export format tools
│       ├── generate_pdf.py
│       ├── generate_docx.py
│       ├── generate_pptx.py
│       ├── generate_markdown.py
│       ├── generate_txt.py
│       └── write_file.py
└── tests/
    ├── test_lesson_generation.py
    ├── test_quiz_generation.py
    ├── test_multi_format_export.py
    ├── test_batch_quiz.py
    ├── test_chat_bound_generation.py
    ├── test_scheduled_generation.py
    ├── test_visibility.py
    ├── test_full_package.py
    └── tools/
        ├── content/
        └── output/
```
