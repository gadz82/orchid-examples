"""Health-check e2e test for the basketball example."""

from __future__ import annotations

import pytest


@pytest.mark.example("basketball")
async def test_health_returns_graph_ready(orchid_test_app) -> None:
    """The /health endpoint reports the graph is built and ready."""
    resp = orchid_test_app.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert data.get("graph_ready") is True
