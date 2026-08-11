"""fm-indexer — Corpus builder for the FM Agent fleet.

Subcommands::

    fm-indexer docs <repo-path>...   — ingest markdown/OpenAPI/config docs
    fm-indexer cards <repo-path>...  — generate derived module cards via Gemini
    fm-indexer kb                    — crawl Help Center sections
    fm-indexer graph <repo-path>...  — extract platform dependency graph
    fm-indexer prune <repo-path>...  — remove vectors for deleted files

For raw Markdown exports with YAML front-matter, use the framework CLI::

    orchid index dir <path> -n <namespace> --front-matter --id-field <field>

All passes are idempotent via a Postgres manifest table
(""indexer_manifest"").  Document IDs = sha256(repo + path +
chunk_ordinal).  Upserts only.  Running twice is a no‑op.
"""

from __future__ import annotations
