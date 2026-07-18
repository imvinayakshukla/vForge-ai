# Extending VForge

The framework is extended through registries and protocols — never by editing
framework code. Three extension points cover most needs.

## 1. Custom LLM provider

Implement `LLMProvider`, register it, and reference it in configuration.
Your job is purely translation: neutral protocol ⇄ vendor API.

```python
# myproviders/echo.py
from vforge.config.models import LLMConfig
from vforge.providers.llm import (
    LLMProvider, LLMResponse, Message, ToolDef, register_provider,
)

@register_provider("echo")
class EchoProvider(LLMProvider):
    """A trivial provider that repeats the last user message."""

    async def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        last = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return LLMResponse(content=f"echo: {last}", stop_reason="end_turn")

    async def aclose(self) -> None:
        pass  # close HTTP clients here
```

```yaml
llm:
  provider: echo
```

Make sure the module is imported before startup (e.g. import it in a small
launcher that then calls `vforge.runtime.serve(...)`, or package it and import
it from an `__init__`).

**Contract details**

- `complete()` receives the *full* history each call (the API is stateless).
- Return `tool_calls` when the model wants tools; the agent loop executes them
  and calls you again with `role="tool"` result messages appended.
- Raise for transport errors — the caller surfaces them; don't swallow.
- Read `self.config` (an `LLMConfig`) for `model`, `api_key`, `base_url`,
  `max_tokens` and the free-form `extra` dict.

## 2. Custom memory backend

Same pattern with `MemoryProvider` — implement, register, configure:

```python
from vforge.config.models import MemoryConfig
from vforge.providers.llm import Message
from vforge.providers.memory import MemoryProvider, register_memory

@register_memory("redis")
class RedisMemory(MemoryProvider):
    def __init__(self, config: MemoryConfig) -> None:
        ...

    async def append(self, session_id: str, message: Message) -> None: ...
    async def history(self, session_id: str) -> list[Message]: ...
    async def clear(self, session_id: str) -> None: ...
    async def sessions(self) -> list[str]: ...
    async def aclose(self) -> None: ...
```

```yaml
memory:
  provider: redis
```

Use `Message.to_dict()` / `Message.from_dict()` for serialization. Preserve
order (oldest first) and never return a history that starts with a `tool`
message or an assistant tool-call turn — models reject orphaned tool results.

## 3. Custom tools

**Prefer an MCP server.** Any process that speaks MCP (stdio or Streamable
HTTP) plugs in via configuration alone, works with every MCP-capable client,
and keeps business logic out of your app process:

```yaml
mcp:
  servers:
    - name: my-tools
      transport: stdio
      command: python
      args: ["-m", "my_mcp_server"]
```

For quick in-process tools (embedding scenarios, tests), attach a
`ToolBinding` after bootstrap:

```python
from vforge.agents import ToolBinding
from vforge.providers.llm import ToolDef

async def now(arguments: dict) -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

binding = ToolBinding(
    definition=ToolDef(
        name="current_time",
        description="Get the current UTC time in ISO-8601 format.",
        input_schema={"type": "object", "properties": {}},
    ),
    executor=now,
)

ctx = await VForgeApp("app-dir").bootstrap()
ctx.agents["assistant"].tools["current_time"] = binding
```

Executors receive the model-supplied arguments dict and return a string.
Return `"ERROR: ..."` (or raise — the loop converts it) to let the model see
and recover from failures.

## Design rules for extensions

- **No business logic in providers or memory backends** — they are plumbing.
- **Async all the way** — use async clients; wrap unavoidable blocking calls
  in `asyncio.to_thread`.
- **Fail fast in `__init__`** — missing packages or config should abort
  startup with a clear message, not fail on the first request.
- **Log through `logging.getLogger(__name__)`** — records automatically get
  correlation IDs and appear in the console's Logs tab.
- **Count things** — `from vforge.observability import metrics`;
  `metrics.increment("myprovider.requests")` shows up in `/api/metrics`.
