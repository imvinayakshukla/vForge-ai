"""Pluggable conversation memory.

The framework ships an in-memory implementation; Redis/PostgreSQL/Mongo/vector
backends can be added by implementing :class:`MemoryProvider` and registering
a factory — no framework changes required.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from vforge.config.models import MemoryConfig
from vforge.providers.llm.base import Message


class MemoryProvider(ABC):
    """Session-scoped conversation storage."""

    @abstractmethod
    async def append(self, session_id: str, message: Message) -> None:
        """Append a message to a session's history."""

    @abstractmethod
    async def history(self, session_id: str) -> list[Message]:
        """Return the full history for a session (oldest first)."""

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        """Delete a session's history."""

    @abstractmethod
    async def sessions(self) -> list[str]:
        """List known session IDs."""

    async def aclose(self) -> None:
        """Release resources (connections etc.)."""


_REGISTRY: dict[str, Callable[[MemoryConfig], MemoryProvider]] = {}


def register_memory(name: str) -> Callable[[type[MemoryProvider]], type[MemoryProvider]]:
    def decorator(cls: type[MemoryProvider]) -> type[MemoryProvider]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def create_memory(config: MemoryConfig) -> MemoryProvider:
    import vforge.providers.memory.in_memory  # noqa: F401  (self-registration)

    factory = _REGISTRY.get(config.provider)
    if factory is None:
        raise ValueError(f"Unknown memory provider '{config.provider}'. Available: {sorted(_REGISTRY)}")
    return factory(config)
