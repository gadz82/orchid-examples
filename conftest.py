"""Parent conftest for all example test suites.

Ensures the ``examples/`` root is on ``sys.path`` so every example test
suite can import shared helpers from ``examples._e2e_shared`` without
needing to set ``PYTHONPATH`` manually.

Also loads the shared e2e fixtures plugin so every example suite gets
``build_orchid_test_app``, ``in_memory_vector_store``, auth fixtures, etc.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Disable API rate limiting for the in-process test suite.  The token-bucket
# dependencies are built when routers are first imported; setting these env
# vars early ensures every TestClient gets no-op limiters.
os.environ.setdefault("RATE_LIMIT_MESSAGES_PER_MINUTE", "0")
os.environ.setdefault("RATE_LIMIT_UPLOADS_PER_MINUTE", "0")
os.environ.setdefault("RATE_LIMIT_INDEX_PER_MINUTE", "0")

pytest_plugins = ["examples._e2e_shared.plugin"]

_EXAMPLES_ROOT = Path(__file__).resolve().parent
if str(_EXAMPLES_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_ROOT))
