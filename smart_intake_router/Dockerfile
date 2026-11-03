# Build context is `workspace-py`, so the image can install the unreleased
# decision-layer framework from this checkout instead of PyPI.
FROM python:3.12-slim

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
COPY examples/smart_intake_router /app/workspace-py/examples/smart_intake_router

RUN pip install -e /app/workspace-py/orchid \
    -e /app/workspace-py/orchid-api \
    -e /app/workspace-py/orchid-storage-sqlite

WORKDIR /app/workspace-py

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=10 \
    CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["uvicorn", "orchid_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
