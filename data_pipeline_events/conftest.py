"""Test plumbing for the direct data-pipeline example."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


def pytest_configure(config):
    config.option.asyncio_mode = "auto"


@pytest.fixture(autouse=True)
def _restore_environment() -> Iterator[None]:
    """Restore os.environ after every test.

    ``Orchid.from_config_path(apply_yaml=True)`` and the CLI's
    ``apply_cli_config`` write YAML values into the process environment. Left
    behind, a startup hook or DSN from this example leaks into the next
    example's app builder.
    """
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)
