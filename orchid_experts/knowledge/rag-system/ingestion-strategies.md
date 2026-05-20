<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx, orchid-website/src/content/examples/rag-strategies.mdx, and codebase analysis -->

# Ingestion Strategies

Ingestion strategies control how documents are split into chunks before embedding and storage in the vector store. Orchid provides multiple strategies, each suited for different document types and retrieval patterns.

## RecursiveIngestion (Default)

The default strategy uses `RecursiveCharacterTextSplitter` to split text using a hierarchy of separators.

### How It Works

1. Tries to split on `\n\n` (paragraphs).
2. If chunks are still too large, tries `\n` (lines).
3. Then `.` (sentences).
4. Then ` ` (words).
5. Finally `` (characters).

It uses the first separator that produces chunks within the target size.

### Configuration

```yaml
upload:
  chunk_size: 1000
  chunk_overlap: 200
```

- **`chunk_size`** — Target maximum characters per chunk. Default: `1000`.
- **`chunk_overlap`** — Characters shared between adjacent chunks. Default: `200`.

### When to Use

- General-purpose documents (markdown, text, documentation).
- Documents with natural paragraph/line structure.
- When you want a balance between chunk size and context preservation.

### Usage

```python
from orchid_ai.documents.strategies import RecursiveIngestion

strategy = RecursiveIngestion()

await ingest_document(
    file_bytes=content.encode("utf-8"),
    filename="doc.md",
    scope=scope,
    namespace="knowledge",
    writer=reader,
    ingestion=strategy,
    pre_extracted_text=content,
)
```

## SemanticIngestion

Splits text based on semantic similarity rather than character boundaries. Uses an embedding model to detect topic shifts and create chunks at natural semantic boundaries.

### How It Works

1. Embeds each sentence or paragraph.
2. Computes cosine similarity between adjacent segments.
3. Splits where similarity drops below a threshold (indicating a topic change).

### When to Use

- Documents with distinct topic sections that don't align with paragraph boundaries.
- When you want chunks that are semantically coherent.
- When character-based splitting produces chunks that span multiple topics.

### Trade-offs

- More expensive (requires embedding each segment during ingestion).
- More accurate semantic boundaries.
- Chunk sizes may vary more than with recursive splitting.

## HierarchicalIngestion

Splits documents into a hierarchy of chunks: large sections for context, smaller chunks for precise retrieval.

### How It Works

1. Splits the document into large sections (e.g., by headings).
2. Within each section, creates smaller chunks.
3. Stores both levels with parent-child relationships.
4. At retrieval time, returns the small matching chunk along with its parent section for context.

### When to Use

- Documents with clear hierarchical structure (e.g., documentation with headings).
- When you need precise retrieval but also want surrounding context.
- When chunk size alone doesn't capture the document's structure.

### Trade-offs

- More complex retrieval logic.
- Better context for retrieved chunks.
- Higher storage cost (stores both parent and child chunks).

## HeaderedIngestion

Splits documents based on markdown headings (H1, H2, H3, etc.), using heading boundaries as natural chunk boundaries.

### How It Works

1. Parses markdown headings.
2. Creates one chunk per heading section (heading + all content until the next heading at the same or higher level).
3. Includes the heading hierarchy in the chunk metadata for context.

### When to Use

- Markdown documents with clear heading structure.
- When headings act as natural topic boundaries.
- When you want chunks that align with document sections.

### Trade-offs

- Chunk sizes may vary significantly (some sections are long, some short).
- Preserves document structure perfectly.
- Heading metadata provides useful context for retrieval.

## Strategy Selection Guide

| Strategy | Best For | Chunk Size | Cost |
|----------|----------|------------|------|
| `RecursiveIngestion` | General documents | Consistent | Low |
| `SemanticIngestion` | Topic-shift detection | Variable | Medium |
| `HierarchicalIngestion` | Structured documents | Two-level | Medium |
| `HeaderedIngestion` | Markdown docs | Variable | Low |

## Custom Ingestion Strategies

To add a custom ingestion strategy:

1. Subclass the ingestion strategy base class.
2. Implement the `split()` method that takes text and returns a list of chunks.
3. Register it with the strategy registry.

```python
from orchid_ai.documents.strategies import register_ingestion_strategy

class MyIngestionStrategy:
    def split(self, text: str) -> list[str]:
        # Custom splitting logic
        return chunks

register_ingestion_strategy("my_strategy", MyIngestionStrategy)
```

Then use it in YAML:

```yaml
rag:
  ingestion_strategy: my_strategy
```
