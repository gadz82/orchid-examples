<!-- Source: derived from orchid/AGENTS.md, orchid-website/src/content/concepts/document-parsing.mdx, and codebase analysis -->

# Document Parsing

Orchid includes a document parsing pipeline that extracts text from various file formats (PDF, DOCX, XLSX, CSV, images) for use in RAG ingestion and prompt context. The pipeline follows the **parse-once pattern** to avoid redundant processing.

## Supported Formats

| Format | Parser | Dependency |
|--------|--------|------------|
| PDF | PyMuPDF (`fitz`) | `pymupdf` |
| DOCX | python-docx | `python-docx` |
| XLSX | OpenPyXL | `openpyxl` |
| CSV | Built-in | Python stdlib |
| Images (PNG, JPG, etc.) | Vision LLM | Configured vision model |

## Parser Registry

Orchid uses a pluggable parser registry that maps file extensions to parser classes:

```python
from orchid_ai.documents.parsers import register_parser, PDFParser

# Register a custom parser for a new format
register_parser(".myformat", MyCustomParser)
```

The built-in parsers are registered automatically at import time.

### Adding a Custom Parser

To add support for a new file format:

1. Create a parser class that implements the parsing interface.
2. Register it with the parser registry.

```python
from orchid_ai.documents.parsers import register_parser

class MyParser:
    async def parse(self, file_bytes: bytes, filename: str) -> str:
        # Extract text from the file
        return extracted_text

register_parser(".myext", MyParser)
```

## The Parse-Once Pattern

The parse-once pattern is a critical design principle in Orchid:

> **Call `extract_text()` once, pass the result to both the prompt builder and `ingest_document(pre_extracted_text=...)`.**

This avoids:

- Parsing the same file twice (once for the prompt, once for RAG ingestion).
- Inconsistent results if the parser is non-deterministic.
- Wasted CPU/memory on redundant parsing.

### Correct Usage

```python
# Parse once
from orchid_ai.documents.pipeline import extract_text

content = await extract_text(file_bytes, filename)

# Use for prompt
prompt = f"Answer based on this document:\n{content}\n\nQuestion: {query}"

# Use for RAG ingestion
await ingest_document(
    file_bytes=file_bytes,
    filename=filename,
    scope=scope,
    namespace=namespace,
    writer=reader,
    ingestion=strategy,
    pre_extracted_text=content,  # Reuse the parsed content
)
```

### Incorrect Usage

```python
# WRONG: Parsing twice
prompt_content = await extract_text(file_bytes, filename)
await ingest_document(
    file_bytes=file_bytes,
    filename=filename,
    # ... no pre_extracted_text — will parse again
)
```

## Document Ingestion Pipeline

**File:** `documents/pipeline.py`

The ingestion pipeline orchestrates the full flow from file to vector store:

1. **Parse** — Extract text from the file (or use `pre_extracted_text` if provided).
2. **Chunk** — Split the text into chunks using the configured ingestion strategy.
3. **Embed** — Convert each chunk to a vector embedding.
4. **Upsert** — Store the chunks in the vector store with metadata.

### ingest_document()

```python
from orchid_ai.documents.pipeline import ingest_document
from orchid_ai.documents.strategies import RecursiveIngestion
from orchid_ai.rag.scopes import OrchidRAGScope

await ingest_document(
    file_bytes=b"...",
    filename="document.pdf",
    scope=OrchidRAGScope(
        tenant_id="my-tenant",
        user_id="user-123",
        chat_id="",
        agent_id="",
    ),
    namespace="knowledge",
    writer=reader,
    ingestion=RecursiveIngestion(),
    pre_extracted_text=None,  # Or provide pre-parsed text
)
```

### Parameters

- **`file_bytes`** — Raw file bytes.
- **`filename`** — File name (used to determine the parser by extension).
- **`scope`** — `OrchidRAGScope` for hierarchical filtering.
- **`namespace`** — Vector store namespace (collection name).
- **`writer`** — `OrchidVectorWriter` implementation.
- **`ingestion`** — Ingestion strategy (e.g., `RecursiveIngestion()`).
- **`pre_extracted_text`** — Optional pre-parsed text (avoids re-parsing).

## Chunking

The chunking step is controlled by the ingestion strategy. The default `RecursiveIngestion` uses:

- **Chunk size:** 1000 characters.
- **Overlap:** 200 characters.

These can be configured in the `upload` section of `orchid.yml`:

```yaml
upload:
  chunk_size: 1000
  chunk_overlap: 200
```

### Recursive Chunking

`RecursiveCharacterTextSplitter` splits text using a hierarchy of separators:

1. `\n\n` (paragraphs)
2. `\n` (lines)
3. `.` (sentences)
4. ` ` (words)
5. `` (characters)

It tries each separator in order, using the first one that produces chunks within the target size. This produces natural chunk boundaries that respect document structure.

## Image Parsing

Images are parsed using a vision LLM configured in `orchid.yml`:

```yaml
upload:
  vision_model: ollama/minicpm-v
```

The vision model receives the image and returns a text description. This is useful for:

- Screenshots in documentation.
- Diagrams and charts.
- Scanned documents.

### Vision Model Requirements

The vision model must support image input. Supported models include:

- `ollama/minicpm-v` — Local vision model (free, requires Ollama).
- `openai/gpt-4o` — OpenAI's multimodal model.
- `gemini/gemini-1.5-pro` — Google's multimodal model.

## File Upload Pipeline

When a user uploads a file through the API:

1. The file is validated (size limit, allowed types).
2. The text is extracted using the parse-once pattern.
3. The text is included in the prompt for the current conversation.
4. The text is ingested into the vector store for future RAG retrieval.
5. The original file is stored (optional, depending on configuration).

### Size Limits

Configured in `orchid.yml`:

```yaml
upload:
  max_size_mb: 20
```

Files exceeding this limit are rejected with a 413 error.

## Common Pitfalls

- **Not using `pre_extracted_text`** — Causes double parsing, wasting resources and potentially producing inconsistent results.
- **Wrong file extension** — The parser registry uses the file extension to select the parser. A `.pdf` file renamed to `.txt` will use the wrong parser.
- **Vision model not configured** — Image uploads fail if no `vision_model` is configured.
- **Chunk size too small** — Produces too many tiny chunks, increasing embedding costs and retrieval noise.
- **Chunk size too large** — Produces chunks that exceed the LLM context window or contain too much irrelevant information.
