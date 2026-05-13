"""Async test plumbing for ``examples/learning/tests/``."""

from __future__ import annotations


def pytest_configure(config):
    config.option.asyncio_mode = "auto"
