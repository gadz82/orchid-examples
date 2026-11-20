"""Docker-free contract test for the event-driven data-pipeline runner."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

WORKSPACE = Path(os.environ.get("ORCHID_WORKSPACE_PY", Path(__file__).resolve().parents[3]))
SCRIPT = WORKSPACE / "script" / "start_data_pipeline_events.sh"
COMPOSE = Path(
    os.environ.get(
        "ORCHID_DATA_PIPELINE_EVENTS_COMPOSE",
        WORKSPACE / "examples" / "data_pipeline_events" / "docker-compose.yml",
    )
)
MAKEFILE = WORKSPACE / "Makefile"

pytestmark = pytest.mark.skipif(
    not SCRIPT.is_file() or not MAKEFILE.is_file(),
    reason="runner test requires the workspace-py monorepo layout",
)


def _env() -> dict[str, str]:
    return {**os.environ, "DATA_PIPELINE_EVENTS_COMPOSE": str(COMPOSE)}


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        env=env or _env(),
    )


def test_runner_exists_and_is_executable() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_runner_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "BASH_SOURCE[0]" in text
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True, timeout=30)


def test_dry_run_does_not_invoke_docker(tmp_path: Path) -> None:
    marker = tmp_path / "docker-called"
    fake = tmp_path / "docker"
    fake.write_text(f"#!/bin/sh\ntouch {marker}\nexit 99\n", encoding="utf-8")
    fake.chmod(0o755)
    env = {**_env(), "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}"}
    result = _run("--dry-run", env=env)
    assert not marker.exists()
    assert "docker compose" in result.stdout
    assert str(COMPOSE) in result.stdout
    assert "up -d --wait" in result.stdout


def test_dry_run_preserves_flag_order() -> None:
    result = _run("--dry-run", "--build", "--force-recreate")
    assert result.stdout.strip().endswith("up -d --wait --build --force-recreate")


def test_dry_run_uses_docker_bin_when_set() -> None:
    env = {**_env(), "DOCKER_BIN": "/custom/docker"}
    result = _run("--dry-run", env=env)
    assert result.stdout.startswith("/custom/docker compose")


def test_clean_volumes_is_printed_in_order() -> None:
    result = _run("--dry-run", "--clean-volumes")
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 2
    assert "down -v" in lines[0]
    assert "up -d --wait" in lines[1]


def test_makefile_target_resolves() -> None:
    result = subprocess.run(
        ["make", "-C", str(WORKSPACE), "-n", "demo-data_pipeline_events"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert "script/start_data_pipeline_events.sh" in result.stdout
    make_compose = WORKSPACE / "examples" / "data_pipeline_events" / "docker-compose.yml"
    if make_compose.is_file():
        result = subprocess.run(
            ["make", "-C", str(WORKSPACE), "-n", "run-data_pipeline_events"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        assert "examples/data_pipeline_events/docker-compose.yml" in result.stdout
