# Configuration Reference

Complete reference for `application.yaml`. Unknown keys anywhere are rejected
at startup (typos fail fast). All string values support environment
interpolation:

- `${VAR}` — required; startup fails if unset
- `${VAR:default}` — falls back to `default` when unset

## Top level

```yaml
app:            # application identity
llm:            # global LLM defaults
agents:         # REQUIRED — at least one agent
mcp:            # MCP servers
memory:         # global memory defaults
server:         # HTTP server binding
auth:           # API-key protection
peers:          # remote agents (A2A)
observability:  # logging
rag:            # optional retrieval
```

## `app`

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | str | `vforge-app` | Shown in the agent card, console and logs |
| `description` | str | `""` | Shown in the agent card |

## `llm` (global default; also valid per agent under `agents[].llm`)

| Key | Type | Default | Description |
|---|---|---|---|
| `provider` | str | `anthropic` | `anthropic` \| `openai` \| `azure_openai` \| `gemini` \| `ollama` \| any registered custom provider |
| `model` | str | provider default | Model ID (Azure: deployment name). Anthropic default: `claude-opus-4-8` |
| `api_key` | str | — | Falls back to the provider SDK's own env-var resolution when omitted |
| `base_url` | str | — | Override endpoint. **Required** for `azure_openai` (your Azure endpoint). Optional for `ollama` (default `http://localhost:11434/v1`) |
| `api_version` | str | `2024-06-01` | Azure OpenAI only |
| `max_tokens` | int | `16000` | Per-response output cap |
| `extra` | map | `{}` | Passed through verbatim to the provider request (escape hatch) |

## `agents[]` (required, ≥ 1; names must be unique)

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | str | required | Agent identifier (A2A skill id, console name) |
| `description` | str | `""` | Used in discovery and the console |
| `prompt` | path | — | System prompt file, relative to the app dir. One of `prompt`/`system` is **required** |
| `system` | str | — | Inline system prompt (alternative to `prompt`) |
| `skills` | list[str] | `[]` | Skill names; each must exist at `skills/<name>/SKILL.md` |
| `mcp_servers` | list[str] | `[]` | Names of configured MCP servers this agent may use |
| `llm` | LLM block | global `llm` | Full per-agent override (replaces, does not merge) |
| `memory` | memory block | global `memory` | Per-agent memory override |
| `max_iterations` | int | `25` | Upper bound on model↔tool loop turns per request |

## `mcp.servers[]`

| Key | Type | Default | Description |
|---|---|---|---|
| `name` | str | required | Referenced by `agents[].mcp_servers` |
| `transport` | str | `stdio` | `stdio` \| `http` |
| `command` | str | — | **Required for stdio** — executable to spawn |
| `args` | list[str] | `[]` | stdio arguments |
| `env` | map | `{}` | Extra environment for the spawned process |
| `url` | str | — | **Required for http** — MCP Streamable HTTP endpoint |
| `headers` | map | `{}` | Extra HTTP headers (auth etc.) |
| `timeout` | float | `30.0` | Per-request timeout, seconds |
| `max_retries` | int | `2` | Tool-call retries (with reconnect + backoff) |

## `memory`

| Key | Type | Default | Description |
|---|---|---|---|
| `provider` | str | `in_memory` | Built-in: `in_memory`; custom backends via `register_memory` |
| `max_messages` | int | `200` | Per-session history cap; trimming never orphans tool results |

## `server`

| Key | Type | Default | Description |
|---|---|---|---|
| `host` | str | `0.0.0.0` | |
| `port` | int | `8000` | |
| `ui_dir` | path | — | Static UI build (e.g. an Angular `dist/.../browser`) served at `/` **instead of** the built-in console. Relative to the app dir; must contain `index.html` (checked at startup). `/a2a`, `/health` and `/api/*` always take precedence. See [webui/angular](../webui/angular/README.md). |

## `auth`

| Key | Type | Default | Description |
|---|---|---|---|
| `api_key` | str | — | When set, `/a2a` and `/api/*` require `X-API-Key` or `Authorization: Bearer`. `/`, `/health` and `/.well-known/agent.json` remain public |

## `peers[]`

Remote agents reachable through `call_next_agent`. Names must not collide
with local agent names.

| Key | Type | Description |
|---|---|---|
| `name` | str | Target name the model uses in `call_next_agent` |
| `url` | str | Base URL of the peer VForge app (the framework appends `/a2a`) |
| `api_key` | str | Sent as `X-API-Key` when the peer has auth enabled |

## `observability`

| Key | Type | Default | Description |
|---|---|---|---|
| `log_level` | str | `INFO` | Standard Python log levels |
| `json_logs` | bool | `false` | Emit JSON lines instead of text |
| `otel.enabled` | bool | `false` | OpenTelemetry tracing. Requires `pip install "vforge[otel]"` (startup fails fast otherwise) |
| `otel.endpoint` | str | — | OTLP/HTTP collector base URL (e.g. `http://localhost:4318`); `/v1/traces` is appended |
| `otel.service_name` | str | `app.name` | `service.name` resource attribute |
| `otel.console_export` | bool | `false` | Also print spans to stdout (debugging) |

When tracing is enabled, VForge emits spans for every HTTP request
(`http.request`), agent turn (`agent.run`), model call (`llm.complete`) and
tool execution (`tool.execute`, `mcp.call_tool`), correctly nested per
conversation turn.

## `rag`

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Requires `pip install "vforge[rag]"` when true |
| `provider` | str | `chroma` | Currently ChromaDB |
| `collection` | str | `vforge` | Chroma collection name |
| `persist_directory` | path | — | Persistent index location; omitted = in-memory |
| `documents_dir` | path | — | Directory indexed at startup |
| `chunk_size` | int | `1000` | Characters per chunk |
| `chunk_overlap` | int | `100` | Overlap between chunks |
| `top_k` | int | `4` | Results returned per query |

## Validation rules (checked at startup / `vforge validate`)

- At least one agent; unique agent names
- Every agent has `prompt` or `system`; referenced prompt files exist
- Referenced skills exist (`skills/<name>/SKILL.md`)
- `agents[].mcp_servers` only reference servers defined under `mcp.servers`
- stdio servers define `command`; http servers define `url`
- Peer names don't collide with local agent names
- No unknown keys anywhere
