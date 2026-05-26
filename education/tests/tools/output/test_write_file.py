from __future__ import annotations

from pathlib import Path

import pytest

from examples.education.tools.output.write_file import WriteFileTool
from orchid_ai.content.local import LocalFileContentSource
from orchid_ai.core.tool import OrchidToolInput


@pytest.mark.asyncio
async def test_write_text(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = WriteFileTool()

    output = await tool.invoke(OrchidToolInput(parameters={"content": "hello world", "filepath": "notes/lesson.txt"}))

    path = Path(output.result["path"])
    assert path.read_text(encoding="utf-8") == "hello world"
    assert output.result["size_bytes"] == path.stat().st_size
    assert path.parts[-3:] == ("default", "notes", "lesson.txt")


@pytest.mark.asyncio
async def test_write_binary(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = WriteFileTool()

    payload = b"\x00\x01orchid"
    output = await tool.invoke(
        OrchidToolInput(parameters={"content": payload, "filepath": "bin/data.bin", "mode": "binary"})
    )

    path = Path(output.result["path"])
    assert path.read_bytes() == payload
    assert output.metadata["mode"] == "binary"


@pytest.mark.asyncio
async def test_path_traversal_blocked(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = WriteFileTool()

    with pytest.raises(ValueError, match="path traversal"):
        await tool.invoke(OrchidToolInput(parameters={"content": "nope", "filepath": "../escape.txt"}))


@pytest.mark.asyncio
async def test_creates_directories(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    tool = WriteFileTool()

    output = await tool.invoke(
        OrchidToolInput(parameters={"content": "nested", "filepath": "deep/tree/lesson/output.txt"})
    )

    path = Path(output.result["path"])
    assert path.exists()
    assert path.parent.is_dir()


@pytest.mark.asyncio
async def test_tenant_scoping(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ORCHID_EXPORT_DIR", str(tmp_path / "exports"))
    source_root = tmp_path / "content"
    source_root.mkdir()
    source = LocalFileContentSource(path=str(source_root), tenant_key="tenant-42")
    tool = WriteFileTool()

    output = await tool.invoke(
        OrchidToolInput(
            parameters={"content": "tenant scoped", "filepath": "artifact.txt"},
            content_sources=[source],
        )
    )

    path = Path(output.result["path"])
    assert "tenant-42" in path.parts
    assert output.metadata["tenant_key"] == "tenant-42"
