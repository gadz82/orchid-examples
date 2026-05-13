# Orchid examples — demo deployment (SQLite + Qdrant)
#
# Build context: examples/
#   docker build -t orchid-demo .
#
# Installs orchid-ai and orchid-api from PyPI, then copies the example
# consumer code (basketball, helpdesk, restaurant agents + storage).
#
# Multi-stage: install deps -> slim runtime

# ── Stage 1: build & install ───────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# Install orchid-api (pulls orchid-ai as transitive dependency).
# Pin >=1.1.0 — 1.1.0 introduces the streaming endpoint
# (/chats/{id}/messages/stream) + MCP auth router that the demo relies on.
RUN pip install --no-cache-dir --prefix=/install "orchid-api>=1.5.0"

# ── Stage 2: runtime ──────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy example source (agents, config, storage, tools)
COPY . examples

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "orchid_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
