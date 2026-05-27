from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

# URL prefix where the API mounts the export directory as static files.
# Must match the mount point in orchid-api/main.py.
_EXPORT_STATIC_MOUNT = "/exports"

_DEFAULT_EXPORT_DIR = "orchid_exports"
_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_segment(value: str) -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("_", value.strip())
    return cleaned or "default"


def _normalise_relative_path(filepath: str) -> Path:
    candidate = PurePosixPath(str(filepath or "").replace("\\", "/"))
    parts = [part for part in candidate.parts if part not in {"", "."}]
    if not parts:
        raise ValueError("filepath must not be empty")
    if candidate.is_absolute() or any(part == ".." for part in parts):
        raise ValueError("path traversal is not allowed")
    return Path(*parts)


def _ensure_extension(filename: str, suffix: str) -> Path:
    relative = _normalise_relative_path(filename)
    if relative.suffix.lower() == suffix.lower():
        return relative
    if relative.suffix:
        return relative.with_suffix(suffix)
    return Path(f"{relative}{suffix}")


def _find_tenant_key(candidate: Any) -> str | None:
    if candidate is None:
        return None
    if isinstance(candidate, dict):
        tenant_key = candidate.get("tenant_key")
        if tenant_key:
            return str(tenant_key)
        for meta_key in ("metadata", "_metadata"):
            meta = candidate.get(meta_key)
            if isinstance(meta, dict) and meta.get("tenant_key"):
                return str(meta["tenant_key"])
        return None
    if isinstance(candidate, (list, tuple, set)):
        for item in candidate:
            tenant_key = _find_tenant_key(item)
            if tenant_key:
                return tenant_key
        return None

    tenant_attr = getattr(candidate, "tenant_key", None)
    if tenant_attr:
        return str(tenant_attr)
    for meta_attr in ("metadata", "_metadata"):
        meta = getattr(candidate, meta_attr, None)
        if isinstance(meta, dict) and meta.get("tenant_key"):
            return str(meta["tenant_key"])
    return None


def _resolve_tenant_key(content_sources: Any = None, auth_context: Any = None) -> str:
    tenant_key = _find_tenant_key(content_sources)
    if not tenant_key and auth_context is not None:
        tenant_key = getattr(auth_context, "tenant_key", None)
    return _sanitize_segment(str(tenant_key or "default"))


def _resolve_export_root(context: dict[str, Any] | None = None) -> Path:
    context_dir = context.get("export_dir") if isinstance(context, dict) else None
    configured = context_dir or os.environ.get("ORCHID_EXPORT_DIR") or _DEFAULT_EXPORT_DIR
    return Path(configured).expanduser().resolve()


def _write_content(
    content: str | bytes | bytearray,
    *,
    filepath: str,
    mode: str = "text",
    context: dict[str, Any] | None = None,
    content_sources: Any = None,
    auth_context: Any = None,
) -> tuple[Path, int, str]:
    if mode not in {"text", "binary"}:
        raise ValueError(f"unsupported write mode: {mode!r}")

    export_root = _resolve_export_root(context)
    tenant_key = _resolve_tenant_key(content_sources=content_sources, auth_context=auth_context)
    target_path = (export_root / tenant_key / _normalise_relative_path(filepath)).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "binary":
        payload = bytes(content) if isinstance(content, (bytes, bytearray)) else str(content).encode("utf-8")
        target_path.write_bytes(payload)
    else:
        payload = content.decode("utf-8") if isinstance(content, (bytes, bytearray)) else str(content)
        target_path.write_text(payload, encoding="utf-8")

    # Build absolute download URL against the API's static mount point.
    # API_BASE_URL is set in docker-compose (defaults to http://localhost:8080).
    relative = target_path.relative_to(export_root)
    api_base = os.environ.get("API_BASE_URL", "").rstrip("/")
    download_url = f"{api_base}{_EXPORT_STATIC_MOUNT}/{relative}"

    return target_path, target_path.stat().st_size, download_url


class WriteFileTool(OrchidTool):
    name = "write_file"
    description = "Write content to the export directory using tenant-scoped relative paths"
    parameters_schema = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Text content to write. Programmatic callers may also pass bytes.",
            },
            "filepath": {
                "type": "string",
                "description": "Relative output path inside the tenant export directory",
            },
            "mode": {
                "type": "string",
                "description": "Write mode: text or binary",
                "default": "text",
                "enum": ["text", "binary"],
            },
        },
        "required": ["content", "filepath"],
    }
    parallel_safe = False

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        parameters = tool_input.parameters
        path, size, download_url = _write_content(
            parameters["content"],
            filepath=parameters["filepath"],
            mode=str(parameters.get("mode", "text")),
            context=tool_input.context,
            content_sources=tool_input.content_sources,
            auth_context=tool_input.auth_context,
        )
        return OrchidToolOutput(
            result={"path": str(path), "size_bytes": size, "download_url": download_url},
            metadata={
                "mode": str(parameters.get("mode", "text")),
                "tenant_key": _resolve_tenant_key(tool_input.content_sources, tool_input.auth_context),
                "export_dir": str(_resolve_export_root(tool_input.context)),
            },
        )
