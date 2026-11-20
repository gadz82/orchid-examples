# Dockerfile — direct data-pipeline example.
#
# Build context is `workspace-py`, so the image uses this checkout's framework
# and API instead of a published wheel:
#   docker compose -f examples/data_pipeline/docker-compose.yml up --build

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/workspace-py

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY orchid /app/workspace-py/orchid
COPY orchid-api /app/workspace-py/orchid-api
COPY orchid-storage-sqlite /app/workspace-py/orchid-storage-sqlite
COPY examples/data_pipeline /app/workspace-py/examples/data_pipeline

RUN pip install -e "/app/workspace-py/orchid[events]" \
    -e /app/workspace-py/orchid-api \
    -e /app/workspace-py/orchid-storage-sqlite

WORKDIR /app/workspace-py

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=10 \
    CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["uvicorn", "orchid_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
