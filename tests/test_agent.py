"""Agent tool-loop tests using the scripted mock provider."""

import pytest

from vforge.agents.agent import Agent, AgentError, ToolBinding
from vforge.config.models import LLMConfig, MemoryConfig
from vforge.providers.llm.base import LLMResponse, ToolCall, ToolDef
from vforge.providers.memory.in_memory import InMemoryProvider

from tests.conftest import MockProvider


def make_agent(provider: MockProvider, tools: dict | None = None, **kwargs) -> Agent:
    return Agent(
        name="test",
        description="",
        system_prompt="You are a test.",
        provider=provider,
        memory=InMemoryProvider(MemoryConfig()),
        tools=tools or {},
        **kwargs,
    )


def echo_tool(record: list) -> ToolBinding:
    async def executor(arguments: dict) -> str:
        record.append(arguments)
        return f"result-for-{arguments.get('value')}"

    return ToolBinding(
        definition=ToolDef(name="echo", description="Echo tool", input_schema={"type": "object"}),
        executor=executor,
    )


async def test_plain_answer():
    provider = MockProvider(LLMConfig(provider="mock"))
    agent = make_agent(provider)
    answer = await agent.run("hello", session_id="s")
    assert answer == "echo: hello"
    history = await agent.memory.history("s")
    assert [m.role for m in history] == ["user", "assistant"]


async def test_tool_loop_executes_and_returns_final():
    provider = MockProvider(LLMConfig(provider="mock"))
    executed: list = []
    agent = make_agent(provider, tools={"echo": echo_tool(executed)})
    provider.script = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="c1", name="echo", arguments={"value": 42})],
            stop_reason="tool_use",
        ),
        LLMResponse(content="done", stop_reason="end_turn"),
    ]

    answer = await agent.run("use the tool")
    assert answer == "done"
    assert executed == [{"value": 42}]
    # second LLM call must have seen the tool result
    second_call = provider.calls[1]
    tool_messages = [m for m in second_call["messages"] if m.role == "tool"]
    assert tool_messages and tool_messages[0].content == "result-for-42"
    assert tool_messages[0].tool_call_id == "c1"


async def test_unknown_tool_reports_error_to_model():
    provider = MockProvider(LLMConfig(provider="mock"))
    agent = make_agent(provider)
    provider.script = [
        LLMResponse(
            content="", tool_calls=[ToolCall(id="c1", name="ghost", arguments={})]
        ),
        LLMResponse(content="recovered"),
    ]
    assert await agent.run("go") == "recovered"
    tool_msg = next(m for m in provider.calls[1]["messages"] if m.role == "tool")
    assert "unknown tool" in tool_msg.content


async def test_failing_tool_is_surfaced_not_raised():
    provider = MockProvider(LLMConfig(provider="mock"))

    async def boom(arguments: dict) -> str:
        raise RuntimeError("kaboom")

    binding = ToolBinding(
        definition=ToolDef(name="boom", description="", input_schema={"type": "object"}),
        executor=boom,
    )
    agent = make_agent(provider, tools={"boom": binding})
    provider.script = [
        LLMResponse(content="", tool_calls=[ToolCall(id="c1", name="boom", arguments={})]),
        LLMResponse(content="handled"),
    ]
    assert await agent.run("go") == "handled"
    tool_msg = next(m for m in provider.calls[1]["messages"] if m.role == "tool")
    assert "kaboom" in tool_msg.content


async def test_max_iterations_guard():
    provider = MockProvider(LLMConfig(provider="mock"))
    executed: list = []
    agent = make_agent(provider, tools={"echo": echo_tool(executed)}, max_iterations=2)
    provider.script = [
        LLMResponse(content="", tool_calls=[ToolCall(id=f"c{i}", name="echo", arguments={})])
        for i in range(3)
    ]
    with pytest.raises(AgentError, match="max_iterations"):
        await agent.run("loop forever")
