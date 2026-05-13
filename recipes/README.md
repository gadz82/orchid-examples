# Recipes — Zero-Infrastructure RAG Example

A recipe knowledge base powered by **ChromaDB** for local, on-disk
vector storage.  No Docker, no Qdrant, no external services.

## What It Demonstrates

- **Zero-infrastructure RAG** — vectors live in `~/.orchid/chroma/`
  via ChromaDB's `PersistentClient`.  No Docker container needed.
- **Orchid CLI with ChromaDB** — the CLI defaults to ChromaDB for
  RAG; this example sets `vector_backend: chroma` explicitly.
- **Startup hook seeding** — `hooks/startup.py` populates 8 recipes
  at bootstrap so agents have material to retrieve.
- **Two agent personas** — `cookbook` (general cooking Q&A) and
  `mealplanner` (dietary-aware meal planning), both querying the
  same recipe corpus.
- **Metadata filtering** — each recipe carries cuisine, course,
  dietary tags, prep time, and difficulty — all available for
  filtered retrieval via the metadata mini-language.

## Prerequisites

- Ollama running with `ollama pull llama3.2`
- `ollama pull nomic-embed-text` (for embeddings, 768-d)
- `pip install -e ../orchid -e ../orchid-cli`

## Usage

```bash
# Install dependencies (run from repo root)
pip install -e orchid -e orchid-cli

# Send a recipe question
orchid chat send "What can I make with chicken?" \
  --config examples/recipes/orchid.yml

# Ask for a meal plan
orchid chat send "Plan a vegan dinner for Monday" \
  --agent mealplanner \
  --config examples/recipes/orchid.yml

# Interactive session
orchid chat interactive --config examples/recipes/orchid.yml

# Check ChromaDB path
ls ~/.orchid/chroma/
```

## File Layout

```
examples/recipes/
├── README.md              # This file
├── __init__.py
├── orchid.yml             # Top-level config (ChromaDB, SQLite, startup hook)
├── agents.yaml            # Agent definitions (cookbook, mealplanner)
└── hooks/
    ├── __init__.py
    └── startup.py         # Seeds 8 recipes into the vector store
```

## Contrast with Qdrant

| Feature | This example (ChromaDB) | Qdrant-based examples |
|---------|------------------------|----------------------|
| Docker required | No | Yes (`qdrant:latest`) |
| Vector storage | `~/.orchid/chroma/` | Qdrant container |
| Sparse/hybrid search | Not supported | Supported |
| Scope promotion | Not supported | Supported |

Set `VECTOR_BACKEND=qdrant` to switch back to Qdrant when hybrid
search or scope promotion is needed.

## Recipe Corpus

The startup hook seeds 8 recipes across 6 cuisines:

| Recipe | Cuisine | Course | Diet |
|--------|---------|--------|------|
| Chicken Parmesan | Italian | Main | Contains dairy |
| Vegetable Stir-Fry | Asian | Main | Vegan, GF option |
| Chocolate Cake | American | Dessert | Contains dairy + gluten |
| Caesar Salad | Italian | Starter | Contains dairy |
| Lentil Soup | Middle Eastern | Main | Vegan, GF |
| Guacamole | Mexican | Starter | Vegan, GF |
| Pad Thai | Thai | Main | GF, contains shellfish |
| Banana Bread | American | Dessert | Vegetarian |
