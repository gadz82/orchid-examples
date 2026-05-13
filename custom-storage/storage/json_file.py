"""
JSON-file ``OrchidChatStorage`` backend — example custom implementation.

Single-process, file-backed chat persistence intended for demos,
embedded apps, and offline notebooks.  All sessions and messages live
in a single JSON document on disk; reads/writes are protected by an
``asyncio.Lock`` so concurrent ``add_message`` calls inside the same
process are serialised.

This backend is **not** suited for production: it has no concurrency
across processes, no indexing for large message volumes, and no
schema migrations.  Use the built-in PostgreSQL or SQLite backends
when those properties matter.

Configuration::

    storage:
      class: examples.custom-storage.storage.json_file.OrchidJSONChatStorage
      dsn: /data/chats.json   # any writeable file path

Contract notes
--------------
* The factory always passes ``dsn=`` and ``extra_migrations_package=``
  to the constructor; both kwargs MUST be accepted, even when (as
  here) the implementation ignores ``extra_migrations_package``.
* ``init_db()`` is awaited once at process startup.  Any backend
  bootstrap (file creation, schema check, index rebuild) belongs
  there — NOT in ``__init__``.
* ``close()`` releases pools/handles.  Failing to flush on close
  loses data; ``close()`` here is a no-op because every mutation
  already persists synchronously.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from orchid_ai.persistence.base import OrchidChatStorage
from orchid_ai.persistence.models import (
    OrchidChatMessage,
    OrchidChatSession,
    utcnow,
)

logger = logging.getLogger(__name__)


class OrchidJSONChatStorage(OrchidChatStorage):
    """File-backed JSON implementation of the chat-storage ABC.

    Layout on disk::

        {
            "sessions": {
                "<chat_id>": { …OrchidChatSession dataclass fields… },
                …
            },
            "messages": {
                "<chat_id>": [ {…OrchidChatMessage…}, … ],
                …
            }
        }

    All datetimes are serialised as ISO-8601 strings so the file is
    human-inspectable.  Round-tripping happens in ``_load`` /
    ``_dump`` — every public method goes through them under the
    instance lock so we never write a partial document.
    """

    def __init__(
        self,
        *,
        dsn: str,
        extra_migrations_package: str | None = None,
    ) -> None:
        # ``dsn`` doubles as the file path.  ``extra_migrations_package``
        # is accepted for contract compliance but ignored — JSON has no
        # schema versioning.
        if not dsn:
            raise ValueError("OrchidJSONChatStorage requires a non-empty `dsn` (file path)")
        if extra_migrations_package:
            logger.info(
                "[OrchidJSONChatStorage] ignoring extra_migrations_package=%r — backend has no migrations",
                extra_migrations_package,
            )

        self._path = Path(os.path.expanduser(dsn))
        self._lock = asyncio.Lock()

    # ── Lifecycle ────────────────────────────────────────────

    async def init_db(self) -> None:
        """Create the file (and parent dirs) if missing."""
        async with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if not self._path.exists():
                self._path.write_text(json.dumps({"sessions": {}, "messages": {}}, indent=2))
                logger.info("[OrchidJSONChatStorage] Initialised empty store at %s", self._path)
            else:
                logger.info("[OrchidJSONChatStorage] Using existing store at %s", self._path)

    async def close(self) -> None:
        """No-op — every mutation already flushed to disk."""

    # ── Sessions ─────────────────────────────────────────────

    async def create_chat(
        self,
        tenant_id: str,
        user_id: str,
        title: str = "",
    ) -> OrchidChatSession:
        async with self._lock:
            db = self._load()
            now = utcnow()
            session = OrchidChatSession(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                user_id=user_id,
                title=title,
                created_at=now,
                updated_at=now,
                is_shared=False,
            )
            db["sessions"][session.id] = self._encode_session(session)
            db["messages"].setdefault(session.id, [])
            self._dump(db)
            return session

    async def list_chats(
        self,
        tenant_id: str,
        user_id: str,
    ) -> list[OrchidChatSession]:
        async with self._lock:
            db = self._load()
            sessions = [
                self._decode_session(row)
                for row in db["sessions"].values()
                if row["tenant_id"] == tenant_id and row["user_id"] == user_id
            ]
            sessions.sort(key=lambda s: s.updated_at, reverse=True)
            return sessions

    async def get_chat(self, chat_id: str) -> OrchidChatSession | None:
        async with self._lock:
            db = self._load()
            row = db["sessions"].get(chat_id)
            return self._decode_session(row) if row else None

    async def delete_chat(self, chat_id: str) -> None:
        async with self._lock:
            db = self._load()
            db["sessions"].pop(chat_id, None)
            db["messages"].pop(chat_id, None)
            self._dump(db)

    async def update_title(self, chat_id: str, title: str) -> None:
        async with self._lock:
            db = self._load()
            row = db["sessions"].get(chat_id)
            if row is None:
                return
            row["title"] = title
            row["updated_at"] = utcnow().isoformat()
            self._dump(db)

    async def mark_shared(self, chat_id: str) -> None:
        async with self._lock:
            db = self._load()
            row = db["sessions"].get(chat_id)
            if row is None:
                return
            row["is_shared"] = True
            row["updated_at"] = utcnow().isoformat()
            self._dump(db)

    # ── Messages ─────────────────────────────────────────────

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        agents_used: list[str] | None = None,
        metadata: dict | None = None,
    ) -> OrchidChatMessage:
        async with self._lock:
            db = self._load()
            if chat_id not in db["sessions"]:
                raise KeyError(f"unknown chat_id: {chat_id!r}")

            message = OrchidChatMessage(
                id=str(uuid.uuid4()),
                chat_id=chat_id,
                role=role,
                content=content,
                agents_used=list(agents_used or []),
                created_at=utcnow(),
                metadata=dict(metadata or {}),
            )
            db["messages"].setdefault(chat_id, []).append(self._encode_message(message))
            db["sessions"][chat_id]["updated_at"] = message.created_at.isoformat()
            self._dump(db)
            return message

    async def get_messages(
        self,
        chat_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OrchidChatMessage]:
        async with self._lock:
            db = self._load()
            rows = db["messages"].get(chat_id, [])
            window = rows[offset : offset + limit]
            return [self._decode_message(r) for r in window]

    # ── Internals ────────────────────────────────────────────

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"sessions": {}, "messages": {}}
        try:
            return json.loads(self._path.read_text())
        except json.JSONDecodeError as exc:
            # Don't silently corrupt the user's data — surface a clear
            # error and abort.
            raise RuntimeError(
                f"chat store at {self._path} is not valid JSON: {exc}. "
                "Move it aside and let init_db() recreate the file."
            ) from exc

    def _dump(self, db: dict[str, Any]) -> None:
        # Atomic-ish write: write to a sibling temp file and rename.
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(db, indent=2, default=str))
        tmp.replace(self._path)

    @staticmethod
    def _encode_session(session: OrchidChatSession) -> dict[str, Any]:
        row = asdict(session)
        row["created_at"] = session.created_at.isoformat()
        row["updated_at"] = session.updated_at.isoformat()
        return row

    @staticmethod
    def _decode_session(row: dict[str, Any]) -> OrchidChatSession:
        return OrchidChatSession(
            id=row["id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            title=row.get("title", ""),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            is_shared=bool(row.get("is_shared", False)),
        )

    @staticmethod
    def _encode_message(message: OrchidChatMessage) -> dict[str, Any]:
        row = asdict(message)
        row["created_at"] = message.created_at.isoformat()
        return row

    @staticmethod
    def _decode_message(row: dict[str, Any]) -> OrchidChatMessage:
        return OrchidChatMessage(
            id=row["id"],
            chat_id=row["chat_id"],
            role=row["role"],
            content=row["content"],
            agents_used=list(row.get("agents_used", [])),
            created_at=datetime.fromisoformat(row["created_at"]),
            metadata=dict(row.get("metadata", {})),
        )
