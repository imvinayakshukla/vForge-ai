"""Anthropic (Claude) provider adapter using the official ``anthropic`` SDK."""

from __future__ import annotations

import logging
from typing import Any

from vforge.config.models import LLMConfig
from vforge.providers.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    ProviderError,
    ToolCall,
    ToolDef,
    register_provider,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-4-8"


@register_provider("anthropic")
class AnthropicProvider(LLMProvider):
    """Claude via the Messages API (async client)."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("The 'anthropic' package is required for provider=anthropic") from exc

        kwargs: dict[str, Any] = {}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self._model = config.model or DEFAULT_MODEL

    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self.config.max_tokens,
            "system": system,
            "messages": _to_anthropic_messages(messages),
            **self.config.extra,
        }
        if tools:
            request["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]

        response = await self._client.messages.create(**request)

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return LLMResponse(
            content="".join(text_parts),
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            usage=usage,
        )

    async def aclose(self) -> None:
        await self._client.close()


def _to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """Translate neutral messages to Anthropic content blocks.

    Consecutive ``tool`` messages are merged into a single user message of
    ``tool_result`` blocks, as required by the Messages API.
    """
    result: list[dict[str, Any]] = []
    pending_tool_results: list[dict[str, Any]] = []

    def flush_tool_results() -> None:
        if pending_tool_results:
            result.append({"role": "user", "content": list(pending_tool_results)})
            pending_tool_results.clear()

    for msg in messages:
        if msg.role == "tool":
            pending_tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content,
                }
            )
            continue
        flush_tool_results()

        if msg.role == "assistant" and msg.tool_calls:
            blocks: list[dict[str, Any]] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            blocks.extend(
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in msg.tool_calls
            )
            result.append({"role": "assistant", "content": blocks})
        else:
            result.append({"role": msg.role, "content": msg.content})

    flush_tool_results()
    return result
