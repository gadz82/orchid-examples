# Wiki RAG example

A two-agent knowledge-base demo showcasing the new RAG pipeline:

| Agent  | Namespace    | Ingestion              | Retrieval           |
| ------ | ------------ | ---------------------- | ------------------- |
| `docs` | `wiki_docs`  | `headered` (800 chars) | `hybrid` (BM25+RRF) |
| `faq`  | `wiki_faq`   | `recursive` (default)  | `simple`            |

Plus a built-in tool (`lookup_glossary`) declared at the YAML top
level with a [per-tool RAG override](../../.knowledge/adr/ADR-024-rag-per-tool-override.md)
— glossary results are cached into the `glossary_cache` namespace
using the `semantic` ingestion strategy, keeping them isolated from
the long-form docs corpus.

## What's interesting

1. **Two ingestion strategies in one config.** The `docs` agent uses
   `headered` so each chunk carries its parent markdown heading. The
   `faq` agent inherits the cheaper `recursive` default — short
   snippets don't benefit from header prepending.

2. **Hybrid retrieval on the docs agent.** Dense recall for semantic
   matches + BM25 for jargon and error codes. Fused via RRF.

3. **Per-tool RAG override (ADR-024).** The `lookup_glossary` tool's
   `rag:` block flips both the namespace and the ingestion strategy.
   When the agent runs the tool with `inject_to_rag: true`, results
   land in `glossary_cache` with `semantic` chunking, not in
   `wiki_docs` with `headered`.

## Running it

```bash
ORCHID_CONFIG=examples/wiki/orchid.yml \
  uvicorn orchid_api.main:app --port 8000
```

Or via CLI:

```bash
orchid chat send "How does hybrid retrieval work?" \
  --agent docs \
  --config examples/wiki/orchid.yml

orchid chat send "How do I disable RAG?" \
  --agent faq \
  --config examples/wiki/orchid.yml
```

## File layout

```
examples/wiki/
├── README.md          (this file)
├── agents.yaml        (two agents + one built-in tool)
├── orchid.yml         (runtime config + startup hook wiring)
└── hooks/
    ├── startup.py     (seeds wiki_docs + wiki_faq corpora)
    └── tools.py       (lookup_glossary handler)
```
