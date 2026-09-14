"""Config-load regression test for the learning example."""

from __future__ import annotations

from pathlib import Path

from orchid_ai.config.loader import load_config


_EXAMPLE_DIR = Path(__file__).resolve().parent.parent


def test_agents_yaml_loads_with_events_and_trigger() -> None:
    """The example agents.yaml parses into a valid events-enabled configuration."""
    config = load_config(str(_EXAMPLE_DIR / "agents.yaml"))

    assert "digest" in config.agents
    assert config.events.enabled is True
    assert config.events.triggers
    trigger_ids = {t.id for t in config.events.triggers}
    assert "weekly-digest" in trigger_ids
