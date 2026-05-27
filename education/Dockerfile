# Dockerfile — Education example
#
# Multi-agent demo: learning content generation with quiz/lesson/export tools.
# Build context: examples/education/
#   docker build -t orchid-education .

FROM python:3.13-slim AS builder

WORKDIR /app

# reportlab needs no extra system deps; python-pptx needs lxml (prebuilt wheel available)
COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/install \
    "orchid-api>=1.8.0" \
    "orchid-rag-qdrant>=0.1.0" \
    -r requirements.txt

# ── Stage 2: runtime ──────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY . examples/education

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "orchid_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
