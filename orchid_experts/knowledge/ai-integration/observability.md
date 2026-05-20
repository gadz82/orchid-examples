<!-- Source: derived from orchid-website/src/content/best-practices.mdx and codebase analysis -->

# Observability

Tools and practices for monitoring and debugging Orchid deployments in production.

## LangSmith Tracing

Enable LangSmith for detailed trace visualization:

```yaml
tracing:
  langsmith_tracing: true
  langsmith_api_key: ${LANGSMITH_API_KEY}
  langsmith_project: my-project
```

LangSmith captures:
- Full agent graph execution traces.
- LLM calls with inputs and outputs.
- Tool call arguments and results.
- RAG retrieval with source documents.
- Supervisor routing decisions.

## OpenTelemetry

Orchid supports OpenTelemetry for distributed tracing:

```python
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Instrument the FastAPI app
FastAPIInstrumentor.instrument_app(app)
```

Provides:
- Cross-service trace context propagation.
- Request latency histograms.
- Error rate metrics.
- Custom spans for agent invocations.

## Structured Logging

Use structured JSON logging for machine-parseable logs:

```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "level": "INFO",
  "logger": "orchid_ai.agents.generic",
  "message": "Agent run completed",
  "correlation_id": "req-abc123",
  "agent": "orchid-framework",
  "duration_ms": 1250,
  "tools_called": ["search_knowledge"],
  "rag_docs_retrieved": 5
}
```

## Correlation IDs

Every request gets a correlation ID for tracing across services:

```
Browser (X-Request-ID: req-123)
  → Frontend (forwards X-Request-ID)
    → API (reads X-Request-ID, attaches to logs)
      → Qdrant (X-Request-ID in metadata)
      → PostgreSQL (X-Request-ID in query comments)
```

## Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Request latency (p95) | Time to complete a turn | >30s |
| Error rate | Percentage of failed requests | >5% |
| SSE connection count | Active streaming connections | >capacity |
| Agent invocation count | Agent runs per minute | Drops to 0 (down) |
| MCP tool latency (p95) | Time per MCP tool call | >10s |
| RAG retrieval latency (p95) | Time per vector search | >1s |
| Token usage per request | Tokens consumed by LLM | >budget per request |
| DB connection pool usage | % of pool in use | >80% |

## Alerting

Set up alerts for:
1. API health check failures.
2. High error rates.
3. High latency (p95 above threshold).
4. Database connection failures.
5. Qdrant connection failures.
6. Token usage exceeding budget.
7. Disk space low on data stores.

## Dashboard

Recommended Grafana panels:
- Request rate and latency.
- Error rate by endpoint.
- Agent invocation distribution.
- SSE connection count.
- Token usage and cost.
- Database and Qdrant health.
