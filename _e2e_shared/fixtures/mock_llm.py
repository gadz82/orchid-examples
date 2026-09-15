"""Deterministic LLM replacements for hermetic e2e tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolCall
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult


class _ResponseQueue:
    """Shared mutable queue so copies (e.g. from ``with_structured_output``)
    consume responses sequentially."""

    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = responses
        self.index = 0

    def next(self) -> dict[str, Any]:
        if not self.responses:
            return {"content": "fake default response"}
        response = self.responses[self.index % len(self.responses)]
        self.index += 1
        return response


class FakeChatModel(BaseChatModel):
    """A LangChain chat model that returns pre-configured responses.

    Use this in tests to remove non-determinism from LLM calls. The model
    can be configured with a list of responses that are returned in order,
    or with a single response repeated indefinitely.

    Supports text responses, tool calls, and structured-output mode.
    """

    structured_output_schema: Any = None
    _queue: _ResponseQueue | None = None

    def __init__(self, responses: list[dict[str, Any]] | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._queue = _ResponseQueue(responses or [])

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"responses": self._queue.responses if self._queue else []}

    def _next_response(self) -> dict[str, Any]:
        if self._queue is None:
            return {"content": "fake default response"}
        return self._queue.next()

    def _make_message(self, response: dict[str, Any]) -> AIMessage:
        content = response.get("content", "")
        tool_calls = response.get("tool_calls")
        if tool_calls is not None:
            return AIMessage(content=content, tool_calls=tool_calls)
        return AIMessage(content=content)

    def invoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> Any:
        """Return a schema instance in structured-output mode."""
        if self.structured_output_schema is not None:
            response = self._next_response()
            return self._make_structured_output(response)
        return super().invoke(input, config, **kwargs)

    async def ainvoke(self, input: Any, config: Any | None = None, **kwargs: Any) -> Any:
        """Return a schema instance in structured-output mode."""
        if self.structured_output_schema is not None:
            response = self._next_response()
            return self._make_structured_output(response)
        return await super().ainvoke(input, config, **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        response = self._next_response()
        if self.structured_output_schema is not None:
            obj = self._make_structured_output(response)
            generation = ChatGeneration(message=AIMessage(content="", additional_kwargs={"parsed": obj}))
            return ChatResult(generations=[generation])
        message = self._make_message(response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop, run_manager, **kwargs)

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        response = self._next_response()
        content = response.get("content", "")
        # Stream each word as a token for a realistic shape.
        chunks = content.split(" ") if content else [""]
        for chunk in chunks:
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=chunk + " "),
                generation_info={},
            )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        for generation in self._stream(messages, stop, run_manager, **kwargs):
            yield generation

    def bind_tools(
        self,
        tools: list[Any],
        **kwargs: Any,
    ) -> FakeChatModel:
        """Return self; tools are ignored, responses come from config."""
        return self

    def with_structured_output(
        self,
        schema: Any,
        **kwargs: Any,
    ) -> FakeChatModel:
        """Return a copy bound to the given schema sharing the response queue."""
        copy = FakeChatModel(responses=[], structured_output_schema=schema)
        copy._queue = self._queue
        return copy

    def with_retry(self, **kwargs: Any) -> FakeChatModel:
        return self

    def with_fallbacks(self, fallbacks: list[Any]) -> FakeChatModel:
        return self

    def _make_structured_output(self, response: dict[str, Any]) -> Any:
        """Convert a response dict into an instance of the bound schema."""
        if isinstance(response, dict) and "content" in response and len(response) == 1:
            # Plain text response wrapped for structured mode — treat as
            # the ``direct_response`` field when available, otherwise fail
            # with a clear error.
            schema_name = getattr(self.structured_output_schema, "__name__", repr(self.structured_output_schema))
            raise ValueError(
                f"FakeChatModel is in structured-output mode for {schema_name}, "
                "but response only contains 'content'. Use add_structured_response() "
                "or pass a dict matching the schema fields."
            )
        return self.structured_output_schema(**response)


class FakeChatModelFactory:
    """Build :class:`FakeChatModel` instances and patch ``build_chat_model``."""

    def __init__(self) -> None:
        self._responses: list[dict[str, Any]] = []
        self._patch_target: Any = None

    def set_responses(self, *responses: dict[str, Any]) -> FakeChatModelFactory:
        """Replace the configured response queue."""
        self._responses = list(responses)
        return self

    def add_response(self, **response: Any) -> FakeChatModelFactory:
        """Append a response to the queue."""
        self._responses.append(response)
        return self

    def add_text(self, content: str) -> FakeChatModelFactory:
        """Append a plain-text response."""
        self._responses.append({"content": content})
        return self

    def add_tool_calls(
        self, tool_calls: list[ToolCall] | list[dict[str, Any]]
    ) -> FakeChatModelFactory:
        """Append a response with tool_calls."""
        self._responses.append({"content": "", "tool_calls": list(tool_calls)})
        return self

    def add_structured_response(self, **fields: Any) -> FakeChatModelFactory:
        """Append a structured-output response (dict becomes schema instance)."""
        self._responses.append(dict(fields))
        return self

    def build(self) -> FakeChatModel:
        """Create a FakeChatModel from the queued responses."""
        return FakeChatModel(responses=list(self._responses))

    @contextmanager
    def patch(self):
        """Patch ``orchid_ai.llm_factory.build_chat_model`` to return fakes."""
        import orchid_ai.llm_factory as llm_factory_module

        original = llm_factory_module.build_chat_model
        model = self.build()

        def _fake_build_chat_model(model_name: str, **kwargs: Any) -> FakeChatModel:
            return model

        llm_factory_module.build_chat_model = _fake_build_chat_model
        try:
            yield self
        finally:
            llm_factory_module.build_chat_model = original


@pytest.fixture
def fake_chat_model_factory() -> FakeChatModelFactory:
    """Fresh factory for configuring deterministic LLM responses."""
    return FakeChatModelFactory()


@pytest.fixture
def mock_llm_response(fake_chat_model_factory: FakeChatModelFactory):
    """Context-manager fixture that patches build_chat_model for a test.

    Example::

        async def test_something(mock_llm_response):
            with mock_llm_response.patch():
                mock_llm_response.add_text("hello")
                # ... run code that calls LLM
    """
    return fake_chat_model_factory
