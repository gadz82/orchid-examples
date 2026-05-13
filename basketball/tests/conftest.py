"""Async test plumbing for ``examples/basketball/tests/``.

Sets ``asyncio_mode = auto`` for this directory at collection time
via the pytest-asyncio plugin's hook so async tests + async
fixtures Just Work without per-test ``@pytest.mark.asyncio``
boilerplate, mirroring the orchid library's own pyproject setting.
"""

from __future__ import annotations


def pytest_configure(config):
    config.option.asyncio_mode = "auto"
