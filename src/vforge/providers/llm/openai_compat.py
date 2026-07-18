"""Providers speaking the OpenAI Chat Completions protocol.

Covers OpenAI itself plus Azure OpenAI, Google Gemini (OpenAI-compatible
endpoint) and Ollama, all through the official ``openai`` SDK.
"""

from __future__ import annotations

import json
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

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"


class OpenAICompatProvider(LLMProvider):
    """Base adapter for any OpenAI-Chat-Completions-compatible backend."""

    default_model: str = "gpt-4o"

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._client = self._build_client(config)
        self._model = config.model or self.default_model

    def _build_client(self, config: LLMConfig):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise ProviderError(
                f"The 'openai' package is required for provider={config.provider}"
            ) from exc
        kwargs: dict[str, Any] = {}
        if config.api_key:
            kwargs["api_key"] = config.api_key
        if config.base_url:
            kwargs["base_url"] = config.base_url
        return openai.AsyncOpenAI(**kwargs)

    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "system", "content": system}, *_to_openai_messages(messages)],
            **self.config.extra,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in tools
            ]

        response = await self._client.chat.completions.create(**payload)
        choice = response.choices[0]

        tool_calls: list[ToolCall] = []
        for call in choice.message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                logger.warning("Malformed tool arguments from model for %s", call.function.name)
                arguments = {}
            tool_calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))

        usage: dict[str, int] = {}
        if response.usage:
            usage = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            }
        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            stop_reason=choice.finish_reason,
            usage=usage,
        )

    async def aclose(self) -> None:
        await self._client.close()


@register_provider("openai")
class OpenAIProvider(OpenAICompatProvider):
    """OpenAI-hosted models."""


@register_provider("azure_openai")
class AzureOpenAIProvider(OpenAICompatProvider):
    """Azure OpenAI deployments (``model`` is the deployment name)."""

    def _build_client(self, config: LLMConfig):
        try:
            import openai
        except ImportError as exc:  # pragma: no cover
            raise ProviderError("The 'openai' package is required for provider=azure_openai") from exc
        if not config.base_url:
            raise ProviderError("azure_openai requires 'base_url' (your Azure endpoint)")
        return openai.AsyncAzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.base_url,
            api_version=config.api_version or "2024-06-01",
        )


@register_provider("gemini")
class GeminiProvider(OpenAICompatProvider):
    """Google Gemini via its OpenAI-compatible endpoint."""

    default_model = "gemini-2.0-flash"

    def _build_client(self, config: LLMConfig):
        if not config.base_url:
            config = config.model_copy(update={"base_url": GEMINI_OPENAI_BASE_URL})
        self.config = config
        return super()._build_client(config)


@register_provider("ollama")
class OllamaProvider(OpenAICompatProvider):
    """Local models served by Ollama."""

    default_model = "llama3.1"

    def _build_client(self, config: LLMConfig):
        updates: dict[str, Any] = {}
        if not config.base_url:
            updates["base_url"] = OLLAMA_DEFAULT_BASE_URL
        if not config.api_key:
            updates["api_key"] = "ollama"  # SDK requires a non-empty key
        if updates:
            config = config.model_copy(update=updates)
        self.config = config
        return super()._build_client(config)


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for msg in messages:
        if msg.role == "tool":
            result.append(
                {"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content}
            )
        elif msg.role == "assistant" and msg.tool_calls:
            result.append(
                {
                    "role": "assistant",
                    "content": msg.content or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in msg.tool_calls
                    ],
                }
            )
        else:
            result.append({"role": msg.role, "content": msg.content})
    return result
