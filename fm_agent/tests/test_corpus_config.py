"""Tests for corpus exclusion configuration."""

from __future__ import annotations

from examples.fm_agent.indexer.walker import ExclusionConfig


class TestExclusionConfig:
    """Cover loading of exclusion rules and Help Center sections."""

    def test_from_file_loads_patterns_and_paths(self, tmp_path) -> None:
        path = tmp_path / "exclusions.yml"
        path.write_text("""
exclude_patterns:
  - .env*
  - "*.pem"
exclude_paths:
  - hydra/apps/notifications
help_center_sections:
  - id: "1"
    name: Notifications
    url: https://help.example.com/sections/1
help_center_base_url: https://help.example.com/hc/en-us
""")
        config = ExclusionConfig.from_file(str(path))

        assert ".env*" in config.exclude_patterns
        assert "*.pem" in config.exclude_patterns
        assert "hydra/apps/notifications" in config.exclude_paths
        assert len(config.help_center_sections) == 1
        assert config.help_center_sections[0]["id"] == "1"
        assert config.help_center_base_url == "https://help.example.com/hc/en-us"

    def test_default_values_when_file_missing(self, tmp_path) -> None:
        config = ExclusionConfig.from_file(str(tmp_path / "missing.yml"))

        assert config.exclude_patterns == []
        assert config.exclude_paths == []
        assert config.help_center_sections == []
        assert config.help_center_base_url == ""

    def test_default_values_when_file_empty(self, tmp_path) -> None:
        path = tmp_path / "exclusions.yml"
        path.write_text("")
        config = ExclusionConfig.from_file(str(path))

        assert config.exclude_patterns == []
        assert config.exclude_paths == []
        assert config.help_center_sections == []
        assert config.help_center_base_url == ""

    def test_all_globs_includes_defaults_and_config(self, tmp_path) -> None:
        path = tmp_path / "exclusions.yml"
        path.write_text("""
exclude_patterns:
  - custom/**
exclude_paths:
  - hydra/apps/learn
""")
        config = ExclusionConfig.from_file(str(path))
        globs = config.all_globs()

        assert "custom/**" in globs
        assert "hydra/apps/learn" in globs
        assert "node_modules/**" in globs

    def test_all_dirs_includes_defaults_and_config(self, tmp_path) -> None:
        path = tmp_path / "exclusions.yml"
        path.write_text("""
exclude_paths:
  - hydra/apps/learn
""")
        config = ExclusionConfig.from_file(str(path))
        dirs = config.all_dirs()

        assert "hydra" in dirs
        assert "node_modules" in dirs

    def test_fm_agent_exclusions_load(self) -> None:
        """The shipped corpus/exclusions.yml must load and contain Help Center sections."""
        from pathlib import Path

        config_path = Path(__file__).parent.parent / "corpus" / "exclusions.yml"
        config = ExclusionConfig.from_file(str(config_path))

        assert "vendor/**" in config.exclude_patterns
        assert "hydra/apps/notifications" in config.exclude_paths
        assert len(config.help_center_sections) >= 2
        assert config.help_center_base_url.startswith("https://")
