"""Self-tests for the fake LLM fixture."""

from __future__ import annotations

import pytest
from examples._e2e_shared.fixtures.mock_llm import FakeChatModel, FakeChatModelFactory
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture
def factory() -> FakeChatModelFactory:
    return FakeChatModelFactory()


async def test_fake_model_returns_text(factory: FakeChatModelFactory) -> None:
    factory.add_text("hello world")
    model = factory.build()
    result = await model.ainvoke([HumanMessage(content="hi")])
    assert isinstance(result, AIMessage)
    assert result.content == "hello world"


async def test_fake_model_returns_tool_calls(factory: FakeChatModelFactory) -> None:
    factory.add_tool_calls(
        [{"name": "search", "args": {"q": "x"}, "id": "call_1"}]
    )
    model = factory.build()
    result = await model.ainvoke([HumanMessage(content="hi")])
    assert result.tool_calls
    assert result.tool_calls[0]["name"] == "search"


async def test_fake_model_sequential_responses(factory: FakeChatModelFactory) -> None:
    factory.add_text("first").add_text("second")
    model = factory.build()
    r1 = await model.ainvoke([HumanMessage(content="a")])
    r2 = await model.ainvoke([HumanMessage(content="b")])
    assert r1.content == "first"
    assert r2.content == "second"


async def test_fake_model_wraps_around(factory: FakeChatModelFactory) -> None:
    factory.add_text("only")
    model = factory.build()
    for _ in range(3):
        result = await model.ainvoke([HumanMessage(content="x")])
        assert result.content == "only"


async def test_fake_model_streams(factory: FakeChatModelFactory) -> None:
    factory.add_text("one two three")
    model = factory.build()
    chunks = []
    async for chunk in model.astream([HumanMessage(content="x")]):
        chunks.append(chunk.content)
    assert "".join(chunks).strip() == "one two three"


async def test_patch_build_chat_model(factory: FakeChatModelFactory) -> None:
    import orchid_ai.llm_factory as lf

    factory.add_text("patched")
    with factory.patch():
        model = lf.build_chat_model("ollama/llama3.2")
        result = await model.ainvoke([HumanMessage(content="hi")])
        assert result.content == "patched"
    # After patch, factory is restored.
    restored = lf.build_chat_model("ollama/llama3.2")
    assert not isinstance(restored, FakeChatModel)
