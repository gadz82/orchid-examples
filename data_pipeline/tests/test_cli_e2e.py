"""CLI e2e coverage for the direct data-pipeline example.

Uses the real ``orchid pipeline run`` command with a deterministic chat model.
The test is skipped when the CLI package is not present beside the examples
(standalone examples checkout).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory

EXAMPLE = Path(__file__).resolve().parents[1]
CLI_ROOT = Path(os.environ.get("ORCHID_CLI_ROOT", Path(__file__).resolve().parents[3] / "orchid-cli"))
if (CLI_ROOT / "orchid_cli").is_dir():
    sys.path.insert(0, str(CLI_ROOT))
pytest.importorskip("orchid_cli")

from orchid_cli.main import app
from typer.testing import CliRunner

RUNNER = CliRunner()
INPUT = {
    "customer_id": "C-100",
    "regions": [{"region": "north"}, {"region": "south"}],
}


def _factory() -> FakeChatModelFactory:
    factory = FakeChatModelFactory()
    factory.add_structured_response(risk="medium", score=42)
    factory.add_text("Escalation note: schedule a success review this week.")
    factory.add_structured_response(
        headline="Customer C-100 is stable",
        body="Retain the account and review usage next month.",
        risk="medium",
    )
    return factory


@pytest.mark.example("data_pipeline")
def test_cli_run_executes_every_job_kind(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # ``apply_cli_config`` writes the example YAML into os.environ (not only the
    # keys monkeypatch knows about), so snapshot the whole environment and
    # restore it before the next example boots its own startup hook.
    for name in (
        "MCP_TOKEN_STORE_CLASS",
        "MCP_CLIENT_REGISTRATION_STORE_CLASS",
        "MCP_GATEWAY_STATE_STORE_CLASS",
    ):
        monkeypatch.setenv(name, "memory")
    monkeypatch.setenv("CHAT_STORAGE_CLASS", "memory")
    monkeypatch.setenv("CHAT_DB_DSN", str(tmp_path / "chats.db"))
    monkeypatch.setenv("VECTOR_BACKEND", "null")
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("DEV_AUTH_BYPASS", "true")

    factory = _factory()
    with factory.patch():
        result = RUNNER.invoke(
            app,
            [
                "pipeline",
                "run",
                "customer_health",
                "--config",
                str(EXAMPLE / "orchid.yml"),
                "--input-json",
                json.dumps(INPUT),
                "--output",
                "json",
            ],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "succeeded"
    assert payload["output"]["headline"] == "Customer C-100 is stable"
    assert payload["summary"] == "Customer C-100 is stable"
    assert {job["status"] for job in payload["jobs"].values()} == {"succeeded"}
