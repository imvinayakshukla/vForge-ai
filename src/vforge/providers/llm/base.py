"""Provider-agnostic LLM abstraction.

Agents speak this neutral protocol; each provider adapter translates it to a
vendor API. Adding a provider means implementing :class:`LLMProvider` and
registering it — no framework code changes.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from vforge.config.models import LLMConfig

logger = logging.getLogger(__name__)

Role = Literal["user", "assistant", "tool"]


@dataclass(slots=True)
class ToolDef:
    """A tool the model may call, described with a JSON Schema."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(slots=True)
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class Message:
    """A neutral chat message.

    ``tool`` messages carry the result of a tool call and must set
    ``tool_call_id``. Assistant messages may carry ``tool_calls``.
    """

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_calls:
            data["tool_calls"] = [
                {"id": c.id, "name": c.name, "arguments": c.arguments} for c in self.tool_calls
            ]
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data.get("content", "") or "",
            tool_calls=[
                ToolCall(id=c["id"], name=c["name"], arguments=c.get("arguments", {}))
                for c in data.get("tool_calls", [])
            ],
            tool_call_id=data.get("tool_call_id"),
        )


@dataclass(slots=True)
class LLMResponse:
    """A single model turn."""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract LLM backend."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        """Run one model turn over the conversation."""

    async def aclose(self) -> None:
        """Release underlying resources (HTTP clients etc.)."""


class ProviderError(RuntimeError):
    """Raised when an LLM provider cannot be created or fails irrecoverably."""


_REGISTRY: dict[str, Callable[[LLMConfig], LLMProvider]] = {}


def register_provider(name: str) -> Callable[[type[LLMProvider]], type[LLMProvider]]:
    """Class decorator registering an :class:`LLMProvider` under *name*."""

    def decorator(cls: type[LLMProvider]) -> type[LLMProvider]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def available_providers() -> list[str]:
    _ensure_builtin_providers()
    return sorted(_REGISTRY)


def create_provider(config: LLMConfig) -> LLMProvider:
    """Instantiate the provider named in *config*."""
    _ensure_builtin_providers()
    factory = _REGISTRY.get(config.provider)
    if factory is None:
        raise ProviderError(
            f"Unknown LLM provider '{config.provider}'. Available: {available_providers()}"
        )
    logger.info("Creating LLM provider '%s' (model=%s)", config.provider, config.model)
    return factory(config)


def _ensure_builtin_providers() -> None:
    """Import built-in adapters so they self-register (lazy, import-cycle safe)."""
    import vforge.providers.llm.anthropic_provider  # noqa: F401
    import vforge.providers.llm.openai_compat  # noqa: F401
