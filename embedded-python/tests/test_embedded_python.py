"""Direct ``Orchid`` facade tests for the embedded-python example.

These tests mirror the example scripts (01_minimal, 02_multi_turn,
03_streaming, 05_custom_runtime, 06_inline_config) but swap the real
LLM and vector backend for deterministic test doubles so the suite is
hermetic and fast.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from orchid_ai import Orchid, OrchidRuntime, load_config
from orchid_ai.config.schema import (
    OrchidAgentConfig,
    OrchidAgentsConfig,
    OrchidDefaultsConfig,
    OrchidLLMConfig,
    OrchidRAGConfig,
    OrchidRAGDefaultsConfig,
)
from orchid_ai.config.tool_registry import (
    ToolParameter,
    clear as clear_tool_registry,
    register_tool,
)

from examples._e2e_shared.fixtures.mock_llm import FakeChatModelFactory
from examples._e2e_shared.fixtures.mock_vector import InMemoryVectorStore


_EXAMPLE_DIR = Path(__file__).resolve().parent.parent
_CONFIG = _EXAMPLE_DIR / "orchid.yml"


def _direct_response_factory(content: str = "Fake response") -> FakeChatModelFactory:
    """Factory whose structured-output response is a direct answer."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="Answer directly",
        execution="parallel",
        direct_response=content,
    )
    return factory


async def _build_orchid_from_config(
    tmp_path: Path,
    factory: FakeChatModelFactory,
    vector_store: InMemoryVectorStore,
) -> Orchid:
    """Build an Orchid client from the example orchid.yml with test doubles."""
    tmp_root = tmp_path / "embedded"
    tmp_root.mkdir()
    agents_config = _EXAMPLE_DIR.parent / "restaurant" / "config" / "agents.yaml"
    with factory.patch():
        return await Orchid.from_config_path(
            str(_CONFIG),
            agents_config_path=str(agents_config),
            chat_db_dsn=str(tmp_root / "chats.db"),
            checkpointer_type="sqlite",
            checkpointer_dsn=str(tmp_root / "checkpoints.db"),
            vector_backend="null",
            runtime_overrides={
                "chat_model": factory.build(),
                "reader": vector_store.repository(),
            },
        )


async def test_minimal_invoke(tmp_path: Path, in_memory_vector_store: InMemoryVectorStore) -> None:
    """Script 01 — one request returns a response and a chat_id."""
    factory = _direct_response_factory("Today's special is mushroom risotto.")
    async with await _build_orchid_from_config(tmp_path, factory, in_memory_vector_store) as orchid:
        result = await orchid.invoke(
            "What's on the menu today?",
            user_id="alice",
            tenant_id="acme",
        )

    assert result.response
    assert result.chat_id
    assert result.interrupted is False


async def test_multi_turn_reuses_chat_id(tmp_path: Path, in_memory_vector_store: InMemoryVectorStore) -> None:
    """Script 02 — same chat_id carries history across invocations."""
    factory = FakeChatModelFactory()
    factory.add_structured_response(
        reasoning="Answer directly",
        execution="parallel",
        direct_response="Yes, we have vegetarian pasta.",
    )
    factory.add_structured_response(
        reasoning="Answer directly",
        execution="parallel",
        direct_response="It can be made gluten-free on request.",
    )
    factory.add_structured_response(
        reasoning="Answer directly",
        execution="parallel",
        direct_response="It costs 18 USD.",
    )

    chat_id = "embedded-mt-1"
    async with await _build_orchid_from_config(tmp_path, factory, in_memory_vector_store) as orchid:
        turn_1 = await orchid.invoke(
            "Do you have vegetarian pasta?",
            chat_id=chat_id,
            user_id="bob",
            tenant_id="acme",
            persist=False,
        )
        turn_2 = await orchid.invoke(
            "Is that gluten-free?",
            chat_id=chat_id,
            user_id="bob",
            tenant_id="acme",
            persist=False,
        )
        turn_3 = await orchid.invoke(
            "What's the price?",
            chat_id=chat_id,
            user_id="bob",
            tenant_id="acme",
            persist=False,
        )

    assert turn_1.chat_id == chat_id
    assert turn_2.chat_id == chat_id
    assert turn_3.chat_id == chat_id
    assert all(not t.interrupted for t in (turn_1, turn_2, turn_3))


async def test_streaming_yields_updates(tmp_path: Path, in_memory_vector_store: InMemoryVectorStore) -> None:
    """Script 03 — ``client.stream`` emits graph update events."""
    factory = _direct_response_factory("The chef's special is grilled salmon.")

    modes: list[str] = []
    async with await _build_orchid_from_config(tmp_path, factory, in_memory_vector_store) as orchid:
        async for mode, _chunk in orchid.stream(
            "Describe the special.",
            user_id="carol",
            tenant_id="acme",
            stream_mode="updates",
        ):
            modes.append(mode)

    assert modes


async def test_custom_runtime(tmp_path: Path, in_memory_vector_store: InMemoryVectorStore) -> None:
    """Script 05 — build your own ``OrchidRuntime`` and pass it to ``Orchid``."""
    factory = _direct_response_factory("Tonight's specials are truffle pasta and sea bass.")

    config = load_config(str(_EXAMPLE_DIR.parent / "restaurant" / "config" / "agents.yaml"))
    runtime = OrchidRuntime(
        default_model="gemini/gemini-flash-latest",
        chat_model=factory.build(),
        reader=in_memory_vector_store.repository(),
    )

    async with Orchid(config=config, runtime=runtime) as orchid:
        result = await orchid.invoke(
            "What are tonight's specials?",
            user_id="erin",
            tenant_id="acme",
            persist=False,
        )

    assert "specials" in result.response.lower()
    assert result.interrupted is False


async def test_inline_config(tmp_path: Path, in_memory_vector_store: InMemoryVectorStore) -> None:
    """Script 06 — build agents + tools entirely in Python, no YAML."""
    clear_tool_registry()

    def lookup_weather(*, city: str = "", **_kwargs) -> str:
        return f"Sunny, 22°C in {city}."

    register_tool(
        "weather",
        lookup_weather,
        description="Current conditions for a city.",
        parameters={
            "city": ToolParameter(
                name="city",
                type="string",
                description="City name.",
                required=True,
            ),
        },
    )

    factory = _direct_response_factory("It's sunny and 22°C in Tokyo.")

    config = OrchidAgentsConfig(
        version="1",
        defaults=OrchidDefaultsConfig(
            llm=OrchidLLMConfig(model="ollama/llama3.2", temperature=0.1),
            rag=OrchidRAGDefaultsConfig(enabled=False),
        ),
        agents={
            "weatherman": OrchidAgentConfig(
                description="Answers questions about today's weather.",
                prompt="You are a concise weather assistant.",
                rag=OrchidRAGConfig(enabled=False),
                tools=["weather"],
            ),
        },
    )
    runtime = OrchidRuntime(
        default_model="ollama/llama3.2",
        chat_model=factory.build(),
        reader=in_memory_vector_store.repository(),
    )

    try:
        async with Orchid(config=config, runtime=runtime) as orchid:
            result = await orchid.invoke(
                "What's the weather in Tokyo?",
                user_id="finn",
                tenant_id="demo",
                persist=False,
            )
        assert "tokyo" in result.response.lower()
        assert "22°c" in result.response.lower()
    finally:
        clear_tool_registry()
