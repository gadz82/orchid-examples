<!-- Source: derived from orchid-website/src/content/concepts/rag.mdx and codebase analysis -->

# Query Transformers

Query transformers preprocess the user query before it is passed to the retrieval strategy. They can improve retrieval quality by reformulating, decomposing, or expanding the query.

## Reformulate

Rewrites the user query into a form that is more likely to match relevant documents in the vector store.

### How It Works

1. Sends the user query to an LLM with a system prompt that instructs it to reformulate the query for better retrieval.
2. The LLM returns a reformulated query (e.g., adding context, removing ambiguity, using more specific terminology).
3. The reformulated query is passed to the retrieval strategy.

### Example

User query: `"How does it work?"`
Reformulated: `"Explain the mechanism of action for the Orchid multi-agent framework's supervisor routing system."`

### Configuration

```yaml
rag:
  query_transformer: reformulate
```

### When to Use

- When user queries are vague or ambiguous.
- When documents use technical terminology that users may not know.
- When the corpus has a specific vocabulary that differs from natural language queries.

## Decompose

Splits a complex query into multiple sub-queries, each targeting a specific aspect of the original question.

### How It Works

1. Sends the user query to an LLM with a system prompt that instructs it to decompose the query into sub-queries.
2. The LLM returns a list of sub-queries.
3. Each sub-query is passed to the retrieval strategy independently.
4. Results from all sub-queries are combined and deduplicated.

### Example

User query: `"Compare the RAG and MCP systems in Orchid"`
Decomposed:
- `"Explain the RAG system in Orchid"`
- `"Explain the MCP system in Orchid"`
- `"What are the differences between RAG and MCP in Orchid"`

### Configuration

```yaml
rag:
  query_transformer: decompose
  decompose_count: 3
```

### When to Use

- When queries cover multiple topics.
- When you need comprehensive coverage of a complex question.
- When the corpus has distinct sections for different sub-topics.

## Multi-Query

Generates multiple paraphrased versions of the user query to increase the chances of matching relevant documents.

### How It Works

1. Sends the user query to an LLM with a system prompt that instructs it to generate paraphrased versions.
2. The LLM returns N variations of the query.
3. Each variation is passed to the retrieval strategy independently.
4. Results from all variations are combined and deduplicated.

### Example

User query: `"How do I set up OAuth?"`
Multi-query variations:
- `"Configure OAuth authentication in Orchid"`
- `"Steps to enable OAuth integration"`
- `"OAuth setup guide for the framework"`

### Configuration

```yaml
rag:
  query_transformer: multi_query
  multi_query_count: 3
```

### When to Use

- When users may phrase queries differently than the documents.
- When the corpus uses varied terminology.
- When you want broader coverage without the specificity of decomposition.

## HyDE (Hypothetical Document Embeddings)

Generates a hypothetical answer to the query, then uses that answer's embedding for retrieval.

### How It Works

1. Sends the user query to an LLM with a system prompt that instructs it to generate a hypothetical answer.
2. The hypothetical answer is embedded.
3. The embedding is used for similarity search (matching answer content rather than query content).

### Example

User query: `"What is the GenericAgent pipeline?"`
Hypothetical answer: `"The GenericAgent pipeline is a 6-step process that includes RAG retrieval, skill detection, MCP tool calls, built-in tool calls, dynamic RAG injection, and LLM summarization."`
The hypothetical answer's embedding is used to find similar documents.

### Configuration

```yaml
rag:
  query_transformer: hyde
```

### When to Use

- When queries are questions and documents contain answers.
- When the query is too short to match well with documents.
- When you want to match on answer content rather than query content.

## Transformer Configuration

Query transformers can be customized with system prompts:

```yaml
rag:
  query_transformer: reformulate
  reformulate_system_prompt: |
    Rewrite the following query to make it more specific and searchable.
    Focus on key terms and concepts. Remove ambiguity.
```

### Default System Prompts

Each transformer has a built-in default system prompt. Override these to customize the transformation behavior for your domain.

## Combining Transformers with Retrieval Strategies

Query transformers and retrieval strategies are independent and can be combined:

```yaml
rag:
  retrieval_strategy: hybrid
  query_transformer: reformulate
```

This configuration reformulates the query first, then performs hybrid (dense + sparse) retrieval on the reformulated query.

### Recommended Combinations

| Query Transformer | Retrieval Strategy | Use Case |
|-------------------|-------------------|----------|
| `reformulate` | `simple` | Vague queries, general corpus |
| `decompose` | `multi_query` | Complex multi-topic questions |
| `multi_query` | `hybrid` | Varied terminology, broad coverage |
| `hyde` | `simple` | Question-answer matching |
| `reformulate` | `hybrid` | Best overall quality |

## Custom Query Transformers

To add a custom query transformer:

1. Subclass the query transformer base class.
2. Implement the `transform()` method.
3. Register it with the transformer registry.

```python
from orchid_ai.rag.query_transformers import register_query_transformer

class MyTransformer:
    async def transform(self, query: str) -> list[str]:
        # Custom transformation logic
        return [transformed_query]

register_query_transformer("my_transformer", MyTransformer)
```
