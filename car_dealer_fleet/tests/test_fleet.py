"""Integration tests for car-dealer-fleet example."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _data_dir() -> Path:
    return Path(__file__).parent.parent / "data"


def _load_module(name: str, rel_path: str) -> object:
    path = Path(__file__).parent.parent / rel_path
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ═══════════════════════════════════════════════════════════════
# Content source discovery tests
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_content_source_discovers_all_six_documents():
    """All six car specification documents are discoverable."""
    from orchid_ai.content.local import LocalFileContentSource

    source = LocalFileContentSource(path=str(_data_dir()))
    items = await source.list()
    names = {item.name for item in items}
    assert len(names) == 6
    assert "camry-2025-specs.md" in names
    assert "f150-2025-specs.md" in names
    assert "golf-2025-specs.txt" in names
    assert "audi-a4-2025-specs.md" in names
    assert "honda-accord-2025-specs.md" in names
    assert "bmw-3-series-2025-specs.md" in names


@pytest.mark.asyncio
async def test_content_source_reads_documents():
    """Each document can be read and contains expected content."""
    from orchid_ai.content.local import LocalFileContentSource

    source = LocalFileContentSource(path=str(_data_dir()))

    camry = await source.get("camry-2025-specs.md")
    assert "203 hp" in (camry.content or "")

    f150 = await source.get("f150-2025-specs.md")
    assert "EcoBoost" in (f150.content or "")

    audi = await source.get("audi-a4-2025-specs.md")
    assert "261 hp" in (audi.content or "")

    honda = await source.get("honda-accord-2025-specs.md")
    assert "VTEC" in (honda.content or "")
    assert "192 hp" in (honda.content or "")

    bmw = await source.get("bmw-3-series-2025-specs.md")
    assert "382 hp" in (bmw.content or "")


# ═══════════════════════════════════════════════════════════════
# JSON extraction tests (parse LLM output)
# ═══════════════════════════════════════════════════════════════

def test_try_parse_json_array_in_code_block():
    """Parses a JSON array inside a markdown code fence."""
    mod = _load_module("startup", "hooks/startup.py")
    _try_parse_json = mod._try_parse_json

    raw = """```json
[
  {"name": "toyota-expert", "description": "Toyota specialist", "prompt": "P1"},
  {"name": "ford-expert", "description": "Ford specialist", "prompt": "P2"}
]
```"""
    configs = _try_parse_json(raw)
    assert len(configs) == 2
    assert {c["name"] for c in configs} == {"toyota-expert", "ford-expert"}


def test_try_parse_json_single_object():
    """Parses a single JSON object inside a code fence."""
    mod = _load_module("startup", "hooks/startup.py")
    _try_parse_json = mod._try_parse_json

    raw = '```json\n{"name": "toyota-expert", "prompt": "Hello"}\n```'
    configs = _try_parse_json(raw)
    assert len(configs) == 1
    assert configs[0]["name"] == "toyota-expert"


def test_try_parse_json_no_json():
    """Returns empty list when no valid JSON is found."""
    mod = _load_module("startup", "hooks/startup.py")
    _try_parse_json = mod._try_parse_json

    raw = "Sorry, I cannot generate agent configs."
    configs = _try_parse_json(raw)
    assert configs == []


def test_try_parse_json_bare_array():
    """Parses a bare JSON array without markdown fences."""
    mod = _load_module("startup", "hooks/startup.py")
    _try_parse_json = mod._try_parse_json

    raw = '[{"name": "vw-expert", "prompt": "You are a VW expert."}]'
    configs = _try_parse_json(raw)
    assert len(configs) == 1
    assert configs[0]["name"] == "vw-expert"


def test_try_parse_json_filters_invalid():
    """Skips JSON objects missing required fields."""
    mod = _load_module("startup", "hooks/startup.py")
    _try_parse_json = mod._try_parse_json

    raw = """```json
[
  {"name": "valid", "prompt": "ok"},
  {"description": "missing fields", "other": true}
]
```"""
    configs = _try_parse_json(raw)
    assert len(configs) == 1
    assert configs[0]["name"] == "valid"


# ═══════════════════════════════════════════════════════════════
# SQLite helpers tests
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_clear_existing_agents(tmp_path):
    """Clears all agents from the agent_configs table."""
    mod = _load_module("startup", "hooks/startup.py")
    import aiosqlite

    db_path = str(tmp_path / "test.db")

    # Seed some agents
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute(
            """CREATE TABLE IF NOT EXISTS agent_configs (
                name TEXT PRIMARY KEY, config TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        await conn.execute(
            "INSERT INTO agent_configs (name, config) VALUES (?, ?)",
            ("test-agent", json.dumps({"name": "test", "prompt": "hi"})),
        )
        await conn.commit()

    # Clear them
    await mod._clear_existing_agents(db_path)

    # Verify empty
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM agent_configs")
        row = await cursor.fetchone()
        assert row[0] == 0


@pytest.mark.asyncio
async def test_persist_configs(tmp_path):
    """Persists agent configs to SQLite and they can be read back."""
    mod = _load_module("startup", "hooks/startup.py")
    import aiosqlite

    db_path = str(tmp_path / "test.db")

    configs = [
        {"name": "toyota-expert", "description": "T", "prompt": "P1"},
        {"name": "ford-expert", "description": "F", "prompt": "P2"},
    ]

    await mod._persist_configs(db_path, configs)

    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            "SELECT name, config FROM agent_configs ORDER BY name"
        )
        rows = await cursor.fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "ford-expert"
        assert rows[1][0] == "toyota-expert"
        parsed = json.loads(rows[1][1])
        assert parsed["prompt"] == "P1"
        assert parsed["rag"] == {}


# ═══════════════════════════════════════════════════════════════
# Config model tests
# ═══════════════════════════════════════════════════════════════

def test_config_storage_defaults_to_sqlite():
    """OrchidConfigStorageConfig defaults to the SQLite backend."""
    from orchid_ai.config.schema_storage import OrchidConfigStorageConfig

    cfg = OrchidConfigStorageConfig(enabled=True)
    assert "OrchidSQLiteConfigStorage" in cfg.class_path
    assert cfg.dsn == "~/.orchid/chats.db"


def test_config_storage_accepts_postgres_override():
    """OrchidConfigStorageConfig allows overriding to PostgreSQL."""
    from orchid_ai.config.schema_storage import OrchidConfigStorageConfig

    cfg = OrchidConfigStorageConfig(
        enabled=True,
        class_path="orchid_ai.persistence.config_postgres.OrchidPostgresConfigStorage",
        dsn="postgresql://localhost/db",
    )
    assert "Postgres" in cfg.class_path


# ═══════════════════════════════════════════════════════════════
# SQLite config storage framework tests
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sqlite_config_storage_crud():
    """OrchidSQLiteConfigStorage supports full CRUD lifecycle."""
    from orchid_ai.persistence.config_sqlite import OrchidSQLiteConfigStorage

    store = OrchidSQLiteConfigStorage(dsn=":memory:")
    await store.init_db()

    try:
        configs = await store.list_configs()
        assert configs == []

        cfg = {"name": "test-agent", "description": "Test", "prompt": "Hello"}
        row = await store.upsert_config("test-agent", cfg)
        assert row["config"]["prompt"] == "Hello"

        row = await store.get_config("test-agent")
        assert row is not None
        assert row["config"]["prompt"] == "Hello"

        patched = await store.patch_config("test-agent", {"prompt": "Updated"})
        assert patched is not None
        assert patched["config"]["prompt"] == "Updated"

        await store.delete_config("test-agent")
        assert await store.get_config("test-agent") is None

        assert await store.patch_config("nope", {"x": 1}) is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_sqlite_config_storage_upsert_overwrites():
    """upsert_config overwrites existing entries."""
    from orchid_ai.persistence.config_sqlite import OrchidSQLiteConfigStorage

    store = OrchidSQLiteConfigStorage(dsn=":memory:")
    await store.init_db()

    try:
        await store.upsert_config("a", {"name": "a", "description": "First", "prompt": "P1"})
        await store.upsert_config("a", {"name": "a", "description": "Second", "prompt": "P2", "rag": {}})

        row = await store.get_config("a")
        assert row is not None
        assert row["config"]["description"] == "Second"
        assert row["config"]["rag"] == {}
    finally:
        await store.close()
