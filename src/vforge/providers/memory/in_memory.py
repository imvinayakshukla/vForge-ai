"""In-process conversation memory with a per-session message cap."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from vforge.config.models import MemoryConfig
from vforge.providers.llm.base import Message
from vforge.providers.memory.base import MemoryProvider, register_memory


@register_memory("in_memory")
class InMemoryProvider(MemoryProvider):
    """Stores histories in a dict; oldest messages are trimmed past the cap.

    Trimming never strands a ``tool`` message without its preceding assistant
    tool-call turn — trimming continues until the window starts at a ``user``
    or plain ``assistant`` message.
    """

    def __init__(self, config: MemoryConfig) -> None:
        self._max_messages = config.max_messages
        self._store: dict[str, list[Message]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def append(self, session_id: str, message: Message) -> None:
        async with self._lock:
            history = self._store[session_id]
            history.append(message)
            while len(history) > self._max_messages:
                history.pop(0)
                # keep the window starting at a clean boundary
                while history and (history[0].role == "tool" or history[0].tool_calls):
                    history.pop(0)

    async def history(self, session_id: str) -> list[Message]:
        async with self._lock:
            return list(self._store.get(session_id, []))

    async def clear(self, session_id: str) -> None:
        async with self._lock:
            self._store.pop(session_id, None)

    async def sessions(self) -> list[str]:
        async with self._lock:
            return sorted(self._store)
