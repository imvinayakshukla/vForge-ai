"""Orchestration tests: call_next_agent routing."""

from vforge.agents.agent import Agent
from vforge.config.models import LLMConfig, MemoryConfig, PeerConfig
from vforge.orchestration.router import CALL_NEXT_AGENT, Orchestrator
from vforge.providers.memory.in_memory import InMemoryProvider

from tests.conftest import MockProvider


def make_agent(name: str) -> Agent:
    return Agent(
        name=name,
        description=f"{name} agent",
        system_prompt="test",
        provider=MockProvider(LLMConfig(provider="mock")),
        memory=InMemoryProvider(MemoryConfig()),
    )


def build() -> tuple[dict[str, Agent], Orchestrator]:
    agents = {"a": make_agent("a"), "b": make_agent("b")}
    orchestrator = Orchestrator(agents, peers=[PeerConfig(name="remote", url="http://x")])
    orchestrator.attach_to_agents()
    return agents, orchestrator


async def test_local_dispatch():
    _, orchestrator = build()
    result = await orchestrator.dispatch("a", "b", "do something")
    assert result == "echo: do something"


async def test_self_delegation_rejected():
    _, orchestrator = build()
    result = await orchestrator.dispatch("a", "a", "loop")
    assert result.startswith("ERROR")


async def test_unknown_target_lists_available():
    _, orchestrator = build()
    result = await orchestrator.dispatch("a", "ghost", "hi")
    assert "unknown agent" in result
    assert "b" in result and "remote" in result


async def test_tool_attached_with_enum_targets():
    agents, _ = build()
    binding = agents["a"].tools[CALL_NEXT_AGENT]
    schema = binding.definition.input_schema
    assert schema["properties"]["agent"]["enum"] == ["b", "remote"]


async def test_tool_executor_validates_arguments():
    agents, _ = build()
    binding = agents["a"].tools[CALL_NEXT_AGENT]
    result = await binding.executor({})
    assert result.startswith("ERROR")
