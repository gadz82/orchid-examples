"""Async HTTP client wrapper for live-server e2e tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Self

import httpx


class OrchidAPIClient:
    """High-level async client for the orchid-api HTTP surface.

    Use this in live-server tests (tests marked with ``--live`` that run
    against a real docker-compose stack).
    """

    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("OrchidAPIClient must be used as an async context manager")
        return self._client

    async def get_health(self) -> dict[str, Any]:
        """GET /health"""
        resp = await self.client.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def create_chat(self, title: str = "", auth_token: str = "dev-token") -> dict[str, Any]:
        """POST /chats"""
        resp = await self.client.post(
            "/chats",
            json={"title": title},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_chats(self, auth_token: str = "dev-token") -> list[dict[str, Any]]:
        """GET /chats"""
        resp = await self.client.get(
            "/chats",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_chat(self, chat_id: str, auth_token: str = "dev-token") -> None:
        """DELETE /chats/{chat_id}"""
        resp = await self.client.delete(
            f"/chats/{chat_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()

    async def get_messages(
        self,
        chat_id: str,
        limit: int = 50,
        offset: int = 0,
        auth_token: str = "dev-token",
    ) -> list[dict[str, Any]]:
        """GET /chats/{chat_id}/messages"""
        resp = await self.client.get(
            f"/chats/{chat_id}/messages",
            params={"limit": limit, "offset": offset},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def send_message(
        self,
        chat_id: str,
        content: str,
        auth_token: str = "dev-token",
    ) -> dict[str, Any]:
        """POST /chats/{chat_id}/messages"""
        resp = await self.client.post(
            f"/chats/{chat_id}/messages",
            data={"content": content},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def stream_message(
        self,
        chat_id: str,
        content: str,
        auth_token: str = "dev-token",
    ) -> AsyncIterator[str]:
        """POST /chats/{chat_id}/messages/stream (SSE)"""
        async with self.client.stream(
            "POST",
            f"/chats/{chat_id}/messages/stream",
            data={"content": content},
            headers={"Authorization": f"Bearer {auth_token}"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                yield line

    async def upload_document(
        self,
        chat_id: str,
        file_path: Path | str,
        auth_token: str = "dev-token",
    ) -> dict[str, Any]:
        """POST /chats/{chat_id}/upload"""
        path = Path(file_path)
        data = await asyncio.to_thread(path.read_bytes)
        resp = await self.client.post(
            f"/chats/{chat_id}/upload",
            files={"file": (path.name, data, "application/octet-stream")},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def resume(
        self,
        chat_id: str,
        approval: dict[str, Any],
        auth_token: str = "dev-token",
    ) -> dict[str, Any]:
        """POST /chats/{chat_id}/resume"""
        resp = await self.client.post(
            f"/chats/{chat_id}/resume",
            json=approval,
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def share_chat(self, chat_id: str, auth_token: str = "dev-token") -> dict[str, Any]:
        """POST /chats/{chat_id}/share"""
        resp = await self.client.post(
            f"/chats/{chat_id}/share",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()

    async def warm_session(self, auth_token: str = "dev-token") -> dict[str, Any]:
        """POST /session/warm"""
        resp = await self.client.post(
            "/session/warm",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        resp.raise_for_status()
        return resp.json()
