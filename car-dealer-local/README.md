# Car Dealer — Local File Content Source Example

A car dealership agent that searches and reads vehicle specification documents
from a local filesystem directory.

## What It Demonstrates

- **`LocalFileContentSource`** — the framework's built-in filesystem content source
- **Content source tools** — `list_content_files`, `search_content_files`, `read_content_file`
- **Agentic tool-calling** — the agent is prompted to search before answering

## Prerequisites

- Ollama running with `llama3.2`
- `pip install -e ../orchid -e ../orchid-cli`

## Usage

```bash
orchid chat interactive --config examples/car-dealer-local/orchid.yml

> What's the fuel economy of the Toyota Camry?
> Compare the Camry and the Golf — which has better MPG?
> What engine options does the F-150 offer?
```
