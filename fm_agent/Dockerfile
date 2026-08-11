# Dockerfile — FM Agent example
#
# Personal AI assistant fleet: multi-agent deployment with PostgreSQL
# storage, Qdrant RAG, and optional Neo4j graph RAG.
# Build context: examples/fm_agent/
#   docker build -t orchid-fm-agent .
#
# Used by docker-compose.yml in this directory.

FROM python:3.13-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install \
    "orchid-api>=1.8.2" \
    -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . examples/fm_agent

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "orchid_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
