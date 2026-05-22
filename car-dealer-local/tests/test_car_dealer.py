"""Integration tests for car-dealer-local example."""
from __future__ import annotations

from pathlib import Path

import pytest


def _data_dir() -> Path:
    return Path(__file__).parent.parent / "data"


@pytest.mark.asyncio
async def test_local_content_source_lists_car_specs():
    from orchid_ai.content.local import LocalFileContentSource
    source = LocalFileContentSource(root_path=str(_data_dir()))
    items = await source.list()
    names = {item.name for item in items}
    assert names == {"camry-2025-specs.md", "f150-2025-specs.md", "golf-2025-specs.txt"}


@pytest.mark.asyncio
async def test_local_content_source_reads_camry():
    from orchid_ai.content.local import LocalFileContentSource
    source = LocalFileContentSource(root_path=str(_data_dir()))
    item = await source.get("camry-2025-specs.md")
    assert item.content is not None
    assert "203 hp" in item.content
    assert "28 MPG" in item.content


@pytest.mark.asyncio
async def test_local_content_source_search():
    from orchid_ai.content.local import LocalFileContentSource
    source = LocalFileContentSource(root_path=str(_data_dir()))
    results = await source.search("camry")
    names = {item.name for item in results}
    assert "camry-2025-specs.md" in names
    assert len(results) == 1


@pytest.mark.asyncio
async def test_local_content_source_search_no_match():
    from orchid_ai.content.local import LocalFileContentSource
    source = LocalFileContentSource(root_path=str(_data_dir()))
    results = await source.search("ferrari")
    assert results == []


@pytest.mark.asyncio
async def test_local_content_source_lazy_content():
    from orchid_ai.content.local import LocalFileContentSource
    source = LocalFileContentSource(root_path=str(_data_dir()))
    items = await source.list()
    for item in items:
        assert item.content is None


@pytest.mark.asyncio
async def test_local_content_source_limit():
    from orchid_ai.content.local import LocalFileContentSource
    source = LocalFileContentSource(root_path=str(_data_dir()))
    items = await source.list(limit=1)
    assert len(items) == 1
