"""In-memory provider tests."""

from vforge.config.models import MemoryConfig
from vforge.providers.llm.base import Message, ToolCall
from vforge.providers.memory.in_memory import InMemoryProvider


async def test_append_and_history():
    memory = InMemoryProvider(MemoryConfig())
    await memory.append("s1", Message(role="user", content="hi"))
    await memory.append("s1", Message(role="assistant", content="hello"))
    history = await memory.history("s1")
    assert [m.content for m in history] == ["hi", "hello"]


async def test_sessions_are_isolated():
    memory = InMemoryProvider(MemoryConfig())
    await memory.append("a", Message(role="user", content="1"))
    await memory.append("b", Message(role="user", content="2"))
    assert [m.content for m in await memory.history("a")] == ["1"]
    assert await memory.sessions() == ["a", "b"]


async def test_clear():
    memory = InMemoryProvider(MemoryConfig())
    await memory.append("s", Message(role="user", content="x"))
    await memory.clear("s")
    assert await memory.history("s") == []


async def test_trimming_respects_cap_and_boundaries():
    memory = InMemoryProvider(MemoryConfig(max_messages=4))
    for i in range(3):
        await memory.append("s", Message(role="user", content=f"u{i}"))
        await memory.append(
            "s",
            Message(
                role="assistant",
                content="",
                tool_calls=[ToolCall(id=f"c{i}", name="t", arguments={})],
            ),
        )
        await memory.append("s", Message(role="tool", content="r", tool_call_id=f"c{i}"))
    history = await memory.history("s")
    assert len(history) <= 4
    # first surviving message must not be an orphaned tool result / tool-call turn
    assert history[0].role == "user"
