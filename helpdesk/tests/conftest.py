"""Async test plumbing for ``examples/helpdesk/tests/``.

Same pattern as ``examples/basketball/tests/conftest.py`` — opts the
directory into pytest-asyncio's auto mode so async tests + fixtures
work without per-test boilerplate.
"""

from __future__ import annotations


def pytest_configure(config):
    config.option.asyncio_mode = "auto"
