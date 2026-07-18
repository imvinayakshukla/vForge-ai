"""Shared fixtures: a scripted mock LLM provider and a temp application dir."""

from __future__ import annotations

from pathlib import Path

import pytest

from vforge.config.models import LLMConfig
from vforge.providers.llm.base import (
    LLMProvider,
    LLMResponse,
    Message,
    ToolDef,
    register_provider,
)


@register_provider("mock")
class MockProvider(LLMProvider):
    """Returns scripted responses; echoes the last user message by default."""

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self.script: list[LLMResponse] = []
        self.calls: list[dict] = []

    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        self.calls.append({"system": system, "messages": list(messages), "tools": tools or []})
        if self.script:
            return self.script.pop(0)
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return LLMResponse(content=f"echo: {last_user}", stop_reason="end_turn")


@pytest.fixture
def app_dir(tmp_path: Path) -> Path:
    """A minimal valid application directory using the mock provider."""
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "assistant.md").write_text("You are a test assistant.")
    skill = tmp_path / "skills" / "greeting"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("Always greet politely.")

    (tmp_path / "application.yaml").write_text(
        """
app:
  name: test-app
llm:
  provider: mock
  model: mock-model
agents:
  - name: assistant
    description: Test assistant
    prompt: prompts/assistant.md
    skills: [greeting]
  - name: helper
    description: Second agent
    system: You are the helper.
""",
        encoding="utf-8",
    )
    return tmp_path
