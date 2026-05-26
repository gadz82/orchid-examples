from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from orchid_ai.agents.mini_agent_aggregator import aggregator_node_factory
from orchid_ai.agents.mini_agent_decomposer import MiniAgentDecomposition, MiniAgentSubTask
from orchid_ai.agents.mini_agent_node import mini_agent_node_factory
from orchid_ai.core.agent import OrchidAgent
from orchid_ai.core.state import OrchidAuthContext
from orchid_ai.graph.graph import _create_agent_node, _make_fork_router
from orchid_ai.observability import extract_event


class _StructuredResponder:
    def __init__(self, parent: "_ScriptedQuizChatModel") -> None:
        self._parent = parent

    async def ainvoke(self, messages):
        self._parent.decomposer_prompts.append(messages[0]["content"])
        return self._parent.decomposition


class _ScriptedQuizChatModel:
    def __init__(self, *, decomposition: MiniAgentDecomposition, aggregated_markdown: str = "") -> None:
        self.decomposition = decomposition
        self.aggregated_markdown = aggregated_markdown
        self.decomposer_prompts: list[str] = []
        self.aggregator_prompts: list[str] = []

    def with_structured_output(self, _schema):
        return _StructuredResponder(self)

    async def ainvoke(self, messages, **_kwargs):
        self.aggregator_prompts.append(messages[0]["content"])
        return SimpleNamespace(content=self.aggregated_markdown)

    def bind_tools(self, tool_defs):
        return self


class _StubQuizAgent(OrchidAgent):
    def __init__(self, *, config, chat_model, response_text: str) -> None:
        super().__init__(reader=MagicMock(), mcp_clients=[], chat_model=chat_model)
        self._config = config
        self._response_text = response_text
        self.run_calls = 0

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def description(self) -> str:
        return self._config.description

    @property
    def rag_namespace(self) -> str:
        return self._config.rag.namespace

    async def run(self, state) -> dict:
        self.run_calls += 1
        return {
            "messages": [AIMessage(content=self._response_text, name=self.name)],
            "mcp_context": {self.name: {"summary": self._response_text}},
        }


def _merge_state(state: dict, update: dict) -> dict:
    merged = dict(state)
    merged["messages"] = [*(state.get("messages") or []), *(update.get("messages") or [])]

    if update.get("mini_agent_decisions"):
        merged["mini_agent_decisions"] = {
            **(state.get("mini_agent_decisions") or {}),
            **update["mini_agent_decisions"],
        }
    if update.get("mini_agent_outcomes"):
        merged["mini_agent_outcomes"] = {
            **(state.get("mini_agent_outcomes") or {}),
            **update["mini_agent_outcomes"],
        }
    if update.get("mcp_context"):
        merged["mcp_context"] = {
            **(state.get("mcp_context") or {}),
            **update["mcp_context"],
        }
    for key in ("active_agents", "pending_agents", "final_response"):
        if key in update:
            merged[key] = update[key]
    return merged


def _patch_agentic_loop(monkeypatch):
    init_calls: list[dict] = []
    summaries = {
        "quiz-generator.mini_0": (
            "1. [easy] What pigment captures sunlight during photosynthesis?",
            {"generate_questions": "photosynthesis-questions"},
        ),
        "quiz-generator.mini_1": (
            "1. [medium] Which organelle produces most ATP during cellular respiration?",
            {"generate_questions": "respiration-questions"},
        ),
        "quiz-generator.mini_2": (
            (
                "1. [easy] What pigment captures sunlight during photosynthesis?\n"
                "2. [hard] Which enzyme adds nucleotides during DNA replication?"
            ),
            {"generate_questions": "replication-questions"},
        ),
    }

    class _StubLoop:
        def __init__(self, **kwargs):
            init_calls.append(kwargs)
            self._kwargs = kwargs

        async def run(self, _messages):
            return summaries[self._kwargs["agent_name"]]

    monkeypatch.setattr("orchid_ai.agents.agentic_loop.AgenticLoop", _StubLoop)
    return init_calls


@pytest.mark.asyncio
async def test_batch_quiz_from_multiple_files(education_config, auth_context: OrchidAuthContext, sample_text: str, secondary_text: str, monkeypatch) -> None:
    third_text = """# DNA Replication

DNA replication copies genetic information before cell division.
Helicase unwinds the double helix and DNA polymerase adds complementary nucleotides.
Accurate replication preserves the genome for daughter cells.
"""
    quiz_config = education_config.agents["quiz-generator"]
    decomposition = MiniAgentDecomposition(
        should_fork=True,
        sub_tasks=[
            MiniAgentSubTask(
                id="mini_0",
                description="Source 1: Photosynthesis",
                instruction="Draft quiz questions only from the photosynthesis source.",
                allowed_tools=[],
                rationale="This source can be covered independently.",
            ),
            MiniAgentSubTask(
                id="mini_1",
                description="Source 2: Cellular Respiration",
                instruction="Draft quiz questions only from the cellular respiration source.",
                allowed_tools=[],
                rationale="This source can be covered independently.",
            ),
            MiniAgentSubTask(
                id="mini_2",
                description="Source 3: DNA Replication",
                instruction="Draft quiz questions only from the DNA replication source.",
                allowed_tools=[],
                rationale="This source can be covered independently.",
            ),
        ],
        reasoning="Each source file can produce its own question draft in parallel.",
    )
    final_markdown = """# Unified Review Quiz

Total Questions: 3
Covered Concepts: Photosynthesis, Cellular Respiration, DNA Replication

1. [easy] What pigment captures sunlight during photosynthesis?
2. [medium] Which organelle produces most ATP during cellular respiration?
3. [hard] Which enzyme adds nucleotides during DNA replication?
"""
    chat_model = _ScriptedQuizChatModel(
        decomposition=decomposition,
        aggregated_markdown=final_markdown,
    )
    agent = _StubQuizAgent(
        config=quiz_config,
        chat_model=chat_model,
        response_text="[Quiz Generator Agent]\nSingle-source quiz ready.",
    )
    parent_node = _create_agent_node(agent, agent_config=quiz_config)
    init_calls = _patch_agentic_loop(monkeypatch)

    query = (
        "Create one review quiz from these three source files.\n\n"
        f"Source 1:\n{sample_text}\n\n"
        f"Source 2:\n{secondary_text}\n\n"
        f"Source 3:\n{third_text}"
    )
    initial_state = {
        "auth_context": auth_context,
        "messages": [HumanMessage(content=query)],
    }

    decomposed_update = await parent_node(initial_state)
    assert agent.run_calls == 0

    state = _merge_state(initial_state, decomposed_update)
    sends = _make_fork_router("quiz-generator")(state)
    assert isinstance(sends, list)
    assert len(sends) == 3

    mini_node = mini_agent_node_factory(parent_config=quiz_config, chat_model=chat_model, mcp_clients=[])
    mini_messages = []
    for send in sends:
        mini_update = await mini_node(send.arg)
        mini_messages.extend(mini_update.get("messages") or [])
        state = _merge_state(state, mini_update)

    aggregator = aggregator_node_factory(parent_config=quiz_config, chat_model=chat_model)
    aggregated_update = await aggregator(state)

    events = []
    for message in [*decomposed_update["messages"], *mini_messages, *aggregated_update["messages"]]:
        event = extract_event(message)
        if event is not None:
            events.append(event)

    event_names = [name for name, _data in events]
    assert event_names.count("mini_agent.decomposed") == 1
    assert event_names.count("mini_agent.started") == 3
    assert event_names.count("mini_agent.finished") == 3
    assert event_names.count("mini_agent.aggregated") == 1
    assert {data["description"] for name, data in events if name == "mini_agent.started"} == {
        "Source 1: Photosynthesis",
        "Source 2: Cellular Respiration",
        "Source 3: DNA Replication",
    }

    assert len(init_calls) == 3
    assert all(set(call["tool_subset"]) == {"generate_questions", "validate_questions"} for call in init_calls)
    assert "only one source file or chunk is present" in chat_model.decomposer_prompts[0]
    assert "Create one review quiz from these three source files." in chat_model.decomposer_prompts[0]
    assert "merge overlapping questions" in chat_model.aggregator_prompts[0]
    assert "Source 3: DNA Replication" in chat_model.aggregator_prompts[0]

    result = aggregated_update["messages"][1].content
    question_lines = [line for line in result.splitlines() if re.match(r"^\d+\.", line)]
    assert len(question_lines) == 3
    assert len(question_lines) == len(set(question_lines))
    assert "Total Questions: 3" in result
    assert len(aggregated_update["mcp_context"]["quiz-generator"]["mini_outcomes"]) == 3


@pytest.mark.asyncio
async def test_single_file_no_fork(education_config, auth_context: OrchidAuthContext, sample_text: str) -> None:
    quiz_config = education_config.agents["quiz-generator"]
    chat_model = _ScriptedQuizChatModel(
        decomposition=MiniAgentDecomposition(should_fork=False, reasoning="Only one source file was provided."),
    )
    agent = _StubQuizAgent(
        config=quiz_config,
        chat_model=chat_model,
        response_text="[Quiz Generator Agent]\nSingle-source quiz ready.",
    )
    parent_node = _create_agent_node(agent, agent_config=quiz_config)

    state = {
        "auth_context": auth_context,
        "messages": [
            HumanMessage(
                content=(
                    "Build a review quiz from this one source file only.\n\n"
                    f"Source 1:\n{sample_text}"
                )
            )
        ],
    }

    result = await parent_node(state)

    assert agent.run_calls == 1
    assert result["messages"][0].content == "[Quiz Generator Agent]\nSingle-source quiz ready."
    assert extract_event(result["messages"][0]) is None
    assert "only one source file or chunk is present" in chat_model.decomposer_prompts[0]
    assert "Build a review quiz from this one source file only." in chat_model.decomposer_prompts[0]
