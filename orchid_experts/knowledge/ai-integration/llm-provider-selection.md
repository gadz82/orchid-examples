<!-- Source: derived from orchid-website/src/content/best-practices.mdx, orchid-website/src/content/concepts/multi-llm.mdx, and codebase analysis -->

# LLM Provider Selection

Guidelines for choosing the right LLM provider for different Orchid deployment scenarios.

## Provider Comparison

| Provider | Models | Latency | Cost | Quality | Best For |
|----------|--------|---------|------|---------|----------|
| OpenAI | GPT-4o, GPT-4o-mini | Low | Medium-High | Excellent | General purpose |
| Anthropic | Claude Sonnet, Haiku | Low | Medium | Excellent | Long context, reasoning |
| Google | Gemini 2.5 Flash, Pro | Low | Low-Medium | Very Good | Cost-effective quality |
| Groq | Llama 3.3 70B | Very Low | Low | Good | Low-latency inference |
| Ollama | Llama 3.2, others | Variable | Free | Good | Local dev, privacy |

## Selection Criteria

### Latency Requirements

- **Real-time chat** — Use Groq or Gemini Flash (fastest).
- **Batch processing** — Use GPT-4o or Claude (higher latency OK).

### Cost Constraints

- **Budget** — Use Ollama (free) or Gemini Flash (cheapest cloud).
- **Moderate** — Use GPT-4o-mini or Claude Haiku.
- **Premium** — Use GPT-4o or Claude Sonnet for complex reasoning.

### Quality Requirements

- **Simple Q&A** — GPT-4o-mini, Gemini Flash, or Llama 3.2.
- **Complex reasoning** — GPT-4o, Claude Sonnet.
- **Multi-step tool use** — GPT-4o, Claude Sonnet.

### Privacy/Security

- **Sensitive data** — Use Ollama (local, no data leaves your infra).
- **General data** — Any cloud provider.

## Multi-Model Strategy

Use different models for different agents:

```yaml
defaults:
  llm:
    model: "ollama/llama3.2"  # Default: local, free

agents:
  simple-qa:
    description: "Simple question answering"
    # Inherits ollama/llama3.2

  complex-reasoning:
    description: "Complex reasoning tasks"
    llm:
      model: "openai/gpt-4o"  # Override: cloud, high quality

  fast-routing:
    description: "Quick routing decisions"
    llm:
      model: "groq/llama-3.3-70b-versatile"  # Override: fast, cheap
```

## Fallback Strategy

Use a fallback model for resilience:

```yaml
defaults:
  llm:
    model: "openai/gpt-4o"
    fallback_model: "ollama/llama3.2"  # Local fallback
```

If the primary model fails (rate limit, outage), the fallback takes over.

### Recommended Fallbacks

| Primary | Fallback | Rationale |
|---------|----------|-----------|
| OpenAI GPT-4o | Ollama Llama 3.2 | Cloud → local |
| Anthropic Claude | Gemini Flash | Premium → budget |
| Groq Llama 3.3 | Ollama Llama 3.2 | Cloud → local |

## Cost Optimization

- Use cheap models for summarization and routing.
- Use expensive models only for complex reasoning.
- Enable history summarization to reduce token usage.
- Set appropriate `k` values for RAG to limit context tokens.
- Use local models (Ollama) for development.
