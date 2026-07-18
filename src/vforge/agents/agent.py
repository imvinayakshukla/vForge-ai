"""The generic Agent: a tool-use loop over a neutral LLM provider.

An Agent knows nothing about any business domain. Its behaviour comes
entirely from its system prompt (+ skills) and its bound tools (MCP servers,
built-in orchestration tools, RAG retrieval).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from vforge.observability.metrics import metrics
from vforge.providers.llm.base import LLMProvider, Message, ToolCall, ToolDef
from vforge.providers.memory.base import MemoryProvider

logger = logging.getLogger(__name__)

ToolExecutor = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass(slots=True)
class ToolBinding:
    """A tool available to an agent: its schema plus an async executor."""

    definition: ToolDef
    executor: ToolExecutor


class AgentError(RuntimeError):
    """Raised when an agent run fails irrecoverably."""


@dataclass
class Agent:
    """A configured, runnable agent."""

    name: str
    description: str
    system_prompt: str
    provider: LLMProvider
    memory: MemoryProvider
    tools: dict[str, ToolBinding] = field(default_factory=dict)
    max_iterations: int = 25

    @property
    def tool_defs(self) -> list[ToolDef]:
        return [binding.definition for binding in self.tools.values()]

    async def run(self, user_message: str, session_id: str = "default") -> str:
        """Handle one user turn: model ↔ tools loop until a final answer."""
        metrics.increment(f"agent.{self.name}.requests")
        await self.memory.append(session_id, Message(role="user", content=user_message))
        messages = await self.memory.history(session_id)

        with metrics.timer(f"agent.{self.name}.duration"):
            for iteration in range(self.max_iterations):
                response = await self.provider.complete(
                    self.system_prompt, messages, self.tool_defs or None
                )
                metrics.increment(f"agent.{self.name}.llm_calls")

                assistant = Message(
                    role="assistant", content=response.content, tool_calls=response.tool_calls
                )
                messages.append(assistant)
                await self.memory.append(session_id, assistant)

                if not response.tool_calls:
                    return response.content

                for call in response.tool_calls:
                    result = await self._execute_tool(call)
                    tool_msg = Message(role="tool", content=result, tool_call_id=call.id)
                    messages.append(tool_msg)
                    await self.memory.append(session_id, tool_msg)
                logger.info(
                    "Agent '%s' iteration %d: executed %d tool call(s)",
                    self.name, iteration + 1, len(response.tool_calls),
                )

        raise AgentError(
            f"Agent '{self.name}' exceeded max_iterations={self.max_iterations} without finishing"
        )

    async def _execute_tool(self, call: ToolCall) -> str:
        binding = self.tools.get(call.name)
        if binding is None:
            logger.warning("Agent '%s': model requested unknown tool '%s'", self.name, call.name)
            return f"ERROR: unknown tool '{call.name}'"
        metrics.increment(f"agent.{self.name}.tool_calls")
        try:
            with metrics.timer(f"tool.{call.name}.duration"):
                return await binding.executor(call.arguments)
        except Exception as exc:
            # Tool failures are surfaced to the model so it can adapt.
            logger.exception("Tool '%s' failed for agent '%s'", call.name, self.name)
            metrics.increment(f"tool.{call.name}.errors")
            return f"ERROR: tool '{call.name}' failed: {exc}"
