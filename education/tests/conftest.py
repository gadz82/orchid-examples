from __future__ import annotations
# ruff: noqa: E402

from pathlib import Path
import sys

import aiosqlite
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
ORCHID_ROOT = WORKSPACE_ROOT / "orchid"
EXAMPLE_ROOT = WORKSPACE_ROOT / "examples" / "education"

for path in (WORKSPACE_ROOT, ORCHID_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from orchid_ai.config.loader import load_config
from orchid_ai.config.tool_registry import clear, get_tool, load_tools_from_config
from orchid_ai.core.events.dispatcher import OrchidSignalDispatcher
from orchid_ai.core.state import OrchidAuthContext
from orchid_ai.core.tool import OrchidToolInput
from orchid_ai.events.backends.sqlite import SQLiteEventStorage
from orchid_ai.events.processors.asyncio_pool import AsyncioWorkerPoolProcessor
from orchid_ai.events.queues.sqlite import SQLiteSignalQueue
from orchid_ai.events.registry import build_registry_from_config
from orchid_ai.events.runners.graph_runner import GraphJobRunner
from orchid_ai.persistence.models import OrchidChatSession


@pytest.fixture
def education_config():
    return load_config(EXAMPLE_ROOT / "agents.yaml")


@pytest.fixture(autouse=True)
def _loaded_tools(education_config):
    clear()
    load_tools_from_config(education_config.tools)
    yield
    clear()


@pytest.fixture
def auth_context() -> OrchidAuthContext:
    return OrchidAuthContext(
        access_token="test-token",
        tenant_key="education-demo",
        user_id="test-user",
    )


@pytest.fixture
def education_events(education_config):
    assert education_config.events is not None
    return education_config.events


@pytest.fixture
def export_dir(tmp_path: Path) -> Path:
    return tmp_path / "exports"


@pytest.fixture
def sample_text() -> str:
    return """# Photosynthesis

Photosynthesis is the process plants use to convert light energy into chemical energy.
Chlorophyll absorbs sunlight and powers the light-dependent reactions.
The Calvin cycle uses carbon dioxide to build glucose for plant growth.
Water is split during the process, releasing oxygen as a by-product.
"""


@pytest.fixture
def secondary_text() -> str:
    return """# Cellular Respiration

Cellular respiration breaks down glucose to release usable energy in the form of ATP.
Mitochondria host most of the reactions in eukaryotic cells.
Oxygen helps drive the electron transport chain, which produces most ATP.
"""


@pytest.fixture
def run_tool(auth_context: OrchidAuthContext, export_dir: Path):
    async def _run(tool_name: str, parameters: dict, *, context: dict | None = None):
        tool = get_tool(tool_name)
        tool_input = OrchidToolInput(
            parameters=parameters,
            context={"export_dir": str(export_dir), **(context or {})},
            auth_context=auth_context,
        )
        return await tool.invoke(tool_input)

    return _run


class InMemoryChatStorage:
    """Minimum chat-storage surface needed by GraphJobRunner tests."""

    def __init__(self) -> None:
        self._chats: dict[str, OrchidChatSession] = {}
        self.messages: list[dict] = []

    def add_chat(self, chat_id: str, *, owner: str, tenant: str = "education-demo") -> None:
        import datetime as _dt

        now = _dt.datetime.now(tz=_dt.UTC)
        self._chats[chat_id] = OrchidChatSession(
            id=chat_id,
            tenant_id=tenant,
            user_id=owner,
            title="education-chat",
            created_at=now,
            updated_at=now,
        )

    async def get_chat_metadata(self, chat_id: str):
        return self._chats.get(chat_id)

    async def can_write(self, chat: OrchidChatSession, auth) -> bool:
        if chat.tenant_id != auth.tenant_key:
            return False
        if chat.user_id == auth.user_id:
            return True
        return "admin" in (auth.roles or frozenset())

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        agents_used: list[str] | None = None,
        metadata: dict | None = None,
    ) -> dict:
        record = {
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "agents_used": list(agents_used or []),
            "metadata": dict(metadata or {}),
        }
        self.messages.append(record)
        return record


@pytest.fixture
def chat_storage_factory():
    return InMemoryChatStorage


@pytest.fixture
def build_event_runtime(education_config, education_events):
    known_agents = set(education_config.agents)

    async def _build(
        tmp_path: Path,
        *,
        trigger_ids: list[str],
        resolver,
        invoker,
        chat_storage=None,
        db_name: str = "education-events.db",
    ) -> dict:
        dsn = str(tmp_path / db_name)
        conn = await aiosqlite.connect(dsn)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")

        storage = SQLiteEventStorage(conn=conn)
        await storage.init_db()
        queue = SQLiteSignalQueue(conn=conn)

        trigger_map = {trigger.id: trigger for trigger in education_events.triggers}
        selected_triggers = [trigger_map[trigger_id] for trigger_id in trigger_ids]
        registry = build_registry_from_config(
            selected_triggers,
            known_agents=known_agents,
            identity_resolver=resolver,
        )
        dispatcher = OrchidSignalDispatcher(store=storage.signals, queue=queue)
        runner = GraphJobRunner(invoker=invoker, chat_storage=chat_storage)
        processor = AsyncioWorkerPoolProcessor()

        async def _close() -> None:
            await conn.close()

        return {
            "conn": conn,
            "storage": storage,
            "queue": queue,
            "registry": registry,
            "dispatcher": dispatcher,
            "runner": runner,
            "processor": processor,
            "close": _close,
        }

    return _build
