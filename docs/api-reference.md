# API Reference

Two surfaces: the **HTTP API** every running app exposes, and the **Python
API** used to embed or extend the framework.

---

## HTTP API

Interactive OpenAPI docs are served at `/api/docs` on a running app.

When `auth.api_key` is configured, all endpoints except `/`, `/health` and
`/.well-known/agent.json` require `X-API-Key: <key>` (or
`Authorization: Bearer <key>`); failures return `401`.

Every response carries an `X-Correlation-Id` header (echoed from the request
header of the same name, or generated).

### Discovery & health

#### `GET /.well-known/agent.json`

A2A agent card. Local agents are listed as skills.

```json
{
  "name": "assistant-demo",
  "description": "…",
  "version": "0.1.0",
  "url": "/a2a",
  "protocol": "a2a",
  "capabilities": { "streaming": false },
  "skills": [ { "id": "assistant", "name": "assistant", "description": "…" } ]
}
```

#### `GET /health`

```json
{ "status": "ok", "app": "assistant-demo", "version": "0.1.0",
  "uptime_seconds": 12.3, "agents": ["assistant", "researcher"] }
```

### A2A messaging

#### `POST /a2a` — JSON-RPC 2.0

Supported method: **`message/send`**.

Request:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": { "role": "user", "parts": [ { "kind": "text", "text": "Hello" } ] },
    "agent": "assistant",          // optional; defaults to the first agent
    "session_id": "conv-42"        // optional; continue a conversation
  }
}
```

Success:

```json
{ "jsonrpc": "2.0", "id": "1",
  "result": { "role": "agent",
              "parts": [ { "kind": "text", "text": "Hi!" } ],
              "messageId": "…" } }
```

Errors use JSON-RPC error objects (HTTP status stays 200):

| Code | Meaning |
|---|---|
| `-32700` | Parse error (invalid JSON body) |
| `-32600` | Not a valid JSON-RPC 2.0 request |
| `-32601` | Unknown method |
| `-32602` | Bad params (no text part, unknown agent) |
| `-32000` | Agent execution failed |

### Console API

| Endpoint | Returns |
|---|---|
| `GET /api/agents` | `[{name, description, tools, max_iterations}]` |
| `POST /api/chat` | Run one turn. Body: `{agent?, message, session_id?}` → `{agent, session_id, answer}` |
| `GET /api/tools` | Every bound tool with its JSON schema, per agent |
| `GET /api/prompts` | Effective system prompts (skills included), per agent |
| `GET /api/skills` | Loaded skills: `[{name, agents, content}]` |
| `GET /api/sessions` | `[{agent, session_id, messages}]` |
| `GET /api/sessions/{agent}/{session_id}` | Full message history for one session |
| `GET /api/logs` | Recent log lines (ring buffer, max 500) |
| `GET /api/metrics` | `{counters: {...}, timers: {name: {count, avg_ms, max_ms}}}` |
| `GET /api/config` | Effective configuration, secrets redacted (`api_key` → `***`) |
| `GET /` | The developer console — built-in HTML, or your own static build when `server.ui_dir` is set (see the [Angular console](../webui/angular/README.md)) |

The console API is a stable contract: any custom UI (Angular, React, …) can be
served via `server.ui_dir` and consume exactly these endpoints.

---

## Python API

### Embedding the runtime

```python
from vforge.runtime import VForgeApp
from vforge.transport import create_app

vf = VForgeApp("path/to/app-dir")
ctx = await vf.bootstrap()          # config → MCP → agents → orchestration → RAG

answer = await ctx.agent("assistant").run("Hello", session_id="s1")

api = create_app(ctx)               # the FastAPI application, if you want to mount it
await vf.shutdown()                 # graceful: memory → providers → MCP
```

`vforge.runtime.serve(app_dir)` is the blocking convenience wrapper the CLI
uses (bootstrap + uvicorn + graceful shutdown).

### Key types

| Type | Module | Purpose |
|---|---|---|
| `VForgeConfig` | `vforge.config` | Validated root configuration |
| `load_config(app_dir)` | `vforge.config` | Parse + interpolate + validate |
| `RuntimeContext` | `vforge.runtime` | `config`, `app_dir`, `agents`, `mcp`, `orchestrator` |
| `Agent` | `vforge.agents` | `run(message, session_id) -> str`; `tools`, `system_prompt` |
| `ToolBinding` | `vforge.agents` | `ToolDef` + async executor `(dict) -> str` |
| `LLMProvider` | `vforge.providers.llm` | `complete(system, messages, tools) -> LLMResponse` |
| `Message`, `ToolCall`, `ToolDef`, `LLMResponse` | `vforge.providers.llm` | The neutral chat protocol |
| `MemoryProvider` | `vforge.providers.memory` | `append` / `history` / `clear` / `sessions` |
| `MCPManager` | `vforge.mcp` | `connect_all`, `tools_for`, `call_tool`, `aclose` |
| `Orchestrator` | `vforge.orchestration` | `dispatch(caller, target, message)` |
| `metrics` | `vforge.observability` | `increment(name)`, `timer(name)`, `snapshot()` |

### The neutral message protocol

Providers translate this protocol to their vendor API — agents never see
vendor types:

```python
Message(role="user" | "assistant" | "tool",
        content: str,
        tool_calls: list[ToolCall],     # assistant turns that request tools
        tool_call_id: str | None)       # set on role="tool" results

LLMResponse(content: str,
            tool_calls: list[ToolCall],
            stop_reason: str | None,
            usage: dict)                # input_tokens / output_tokens
```

For adding your own providers, memory backends or tools, see
[Extending VForge](extending.md).

### CLI

| Command | Description |
|---|---|
| `vforge start [-d DIR]` | Bootstrap and serve (console, A2A, health) |
| `vforge validate [-d DIR]` | Validate config, prompt files and skills |
| `vforge scaffold NAME [-d DIR]` | Create a new application skeleton |
| `vforge list-tools [-d DIR]` | Connect MCP servers and list discovered tools |
| `vforge doctor [-d DIR]` | Diagnose Python version, packages, config, API keys |
| `vforge version` | Print the framework version |

All commands exit non-zero on failure, making them CI-friendly.
