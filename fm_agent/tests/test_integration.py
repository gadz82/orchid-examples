"""Docker-compose integration test for the FM Agent stack.

This test is skipped by default. Run with:

    pytest tests/test_integration.py -m integration

It requires Docker to be installed and running.
"""

from __future__ import annotations

import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.skipif(not shutil.which("docker"), reason="docker not installed")
def test_compose_health() -> None:
    """Start the Docker stack and verify /health returns 200."""
    compose_dir = Path(__file__).resolve().parents[1]
    env_file = compose_dir / ".env"
    if not env_file.exists():
        pytest.skip("missing .env file; copy .env.example first")

    try:
        subprocess.run(
            ["docker", "compose", "--profile", "default", "up", "-d", "--build"],
            cwd=compose_dir,
            check=True,
            timeout=300,
        )

        url = "http://localhost:8080/health"
        response: urllib.request.addinfourl | None = None
        for _ in range(30):
            try:
                response = urllib.request.urlopen(url, timeout=2)
                break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2)
        else:
            raise RuntimeError(f"health check failed at {url}")

        assert response is not None
        assert response.status == 200
    finally:
        subprocess.run(
            ["docker", "compose", "down"],
            cwd=compose_dir,
            check=False,
        )
