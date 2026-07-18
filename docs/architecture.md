# VForge Architecture

## Design principles

- **Convention over configuration** — sensible defaults everywhere; a minimal
  app is `application.yaml` + one prompt file.
- **Configuration driven** — no agent logic in code; everything comes from
  `application.yaml`.
- **Provider agnostic** — the agent loop speaks a neutral message protocol;
  vendor adapters translate.
- **Protocol first** — MCP for tools, A2A (JSON-RPC) for agent communication.
- **Async first** — every I/O path is `async/await`.
- **No business logic in the framework** — domains live in MCP servers,
  prompts and skills.

## Layers

| Layer | Package | Responsibility |
|---|---|---|
| CLI | `vforge.cli` | `start`, `validate`, `scaffold`, `list-tools`, `doctor`, `version` |
| Web console | `vforge.web` + `/api/*` routes | Developer UI: chat, agents, tools, prompts, skills, sessions, logs, metrics, config. Replaceable via `server.ui_dir` (Angular app in `webui/angular`) |
| Runtime | `vforge.runtime` | Lifecycle (bootstrap/shutdown), runtime context, serving |
| Orchestration | `vforge.orchestration` | `call_next_agent`: local dispatch + A2A peer calls |
| Agents | `vforge.agents` | Generic tool-use loop; factory that wires everything from config |
| Providers | `vforge.providers.llm`, `vforge.providers.memory` | Vendor adapters + registries |
| MCP | `vforge.mcp` | stdio/HTTP transports, discovery, execution, retries |
| Skills | `vforge.skills` | `SKILL.md` loading and prompt composition |
| RAG | `vforge.rag` | Optional Chroma-backed retrieval tool |
| Auth | `vforge.auth` | API-key middleware |
| Observability | `vforge.observability` | Logging, correlation IDs, metrics, optional OpenTelemetry tracing (`span()` is a no-op unless `otel.enabled`) |
| Transport | `vforge.transport` | FastAPI app: A2A endpoints + console API |
| Configuration | `vforge.config` | YAML parsing, env interpolation, Pydantic validation |

Dependencies point downward only; there are no cycles. Adapters register
themselves in registries (`register_provider`, `register_memory`) so new
backends require zero framework changes.

## Distribution model

VForge is consumed **as a versioned library**. An agent project declares
`vforge==X.Y.Z` in its own `pyproject.toml`, supplies `application.yaml` +
`prompts/` + `skills/`, and runs `vforge start`. Framework upgrades are a
dependency-pin bump; agent projects contain no framework code. See
[Getting Started](getting-started.md) → *How an agent project depends on
VForge*.

## Startup sequence (`VForgeApp.bootstrap`)

1. `load_config()` — parse YAML, resolve `${VARS}`, validate, check prompt files
2. `setup_logging()` + `setup_tracing()` — logs, correlation IDs, optional OTel
3. `MCPManager.connect_all()` — handshake + `tools/list` on every server (fail fast)
4. `AgentFactory.build_all()` — per agent: prompt file → + skills → LLM provider
   (global or override) → memory → MCP tool bindings
5. `Orchestrator.attach_to_agents()` — adds `call_next_agent` where targets exist
6. Optional `RAGEngine` — index documents, attach `search_knowledge`
7. Transport (`create_app`) serves A2A + console; uvicorn handles signals, and
   shutdown closes memory backends, providers and MCP connections in order.

## The agent loop

```
user msg ─▶ memory.append ─▶ provider.complete(system, history, tools)
                 ▲                      │
                 │        tool_calls?───┤
                 │            │yes      │no
                 │   execute tools      └─▶ final answer (persisted)
                 │   (MCP / builtin)
                 └── tool results appended, loop (≤ max_iterations)
```

Tool failures are returned to the model as `ERROR: ...` tool results rather
than raised, so agents can adapt. `max_iterations` bounds runaway loops.

## A2A surface

- `GET /.well-known/agent.json` — agent card listing all local agents as skills
- `POST /a2a` — JSON-RPC 2.0, method `message/send`; optional `params.agent`
  selects a local agent, `params.session_id` continues a conversation
- `GET /health` — status, uptime, agent list

`call_next_agent` uses the same protocol when dispatching to `peers`, so a
fleet of VForge apps composes without custom glue.

## Extension points

| Extension | How |
|---|---|
| LLM provider | `@register_provider("x")` on an `LLMProvider` subclass |
| Memory backend | `@register_memory("x")` on a `MemoryProvider` subclass |
| Tools | Any MCP server (stdio or HTTP) |
| Auth scheme | Additional middleware alongside `ApiKeyMiddleware` |
| Web UI | Any static build via `server.ui_dir` (Angular reference app in `webui/angular`) |
| Tracing backend | Any OTLP/HTTP collector via `observability.otel.endpoint` |
