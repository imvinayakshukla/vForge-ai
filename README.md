# ⚒️ VForge

**A configuration-driven framework for building AI agents — "Spring Boot for AI Agents".**

VForge is *not* an agent. It is a reusable framework: you supply
`application.yaml`, `prompts/` and `skills/`, run `vforge start`, and the
framework handles everything else — LLM providers, MCP tools, agent-to-agent
communication, memory, sessions, observability, auth and a developer console.

```
your-agent/
├── application.yaml     # the whole app, declaratively
├── prompts/
│   └── assistant.md     # system prompt
└── skills/
    └── house-style/
        └── SKILL.md     # reusable prompt material
```

```bash
pip install -e ".[dev]"        # from this repo
vforge scaffold my-agent       # create a new app
cd my-agent
export ANTHROPIC_API_KEY=...
vforge start                   # console at http://localhost:8000
```

## What the framework provides

| Layer | What it does |
|---|---|
| **Configuration engine** | Parses `application.yaml`, resolves `${ENV_VARS}`, resolves prompt files and skills, validates with Pydantic, fails fast |
| **LLM provider layer** | `anthropic`, `openai`, `azure_openai`, `gemini`, `ollama` out of the box; add a provider by implementing one adapter and registering it |
| **MCP manager** | stdio + Streamable HTTP transports, tool discovery at startup, retries, reconnection, timeouts |
| **Agent factory** | Builds agents from config, injecting LLM, MCP tools, prompts, skills, memory — you never instantiate agents |
| **A2A transport** | Every app exposes `GET /.well-known/agent.json`, `POST /a2a` (JSON-RPC), `GET /health` |
| **Orchestration** | Built-in `call_next_agent` tool; routes to local agents in-process and to configured `peers` over A2A |
| **Memory** | Pluggable; `in_memory` included, Redis/Postgres/vector implementable via the same interface |
| **Skills** | `skills/<name>/SKILL.md` appended to system prompts |
| **Auth** | Optional API key on `/a2a` and `/api` (`X-API-Key` or bearer) |
| **RAG (optional)** | ChromaDB indexing + `search_knowledge` tool; the framework runs fully without it (`pip install "vforge[rag]"`) |
| **Observability** | Structured logs (text/JSON), correlation IDs, in-process metrics, optional OpenTelemetry tracing (`pip install "vforge[otel]"`) with nested spans per turn |
| **Web console** | Chat, agents, tools, prompts, skills, sessions, logs, metrics, health, config — auto-discovers agents. Replaceable: point `server.ui_dir` at any static build; an [Angular console](webui/angular/README.md) is included |
| **CLI** | `start`, `validate`, `scaffold`, `list-tools`, `doctor`, `version` |

## application.yaml at a glance

```yaml
app:
  name: support-agent

llm:                              # global default, overridable per agent
  provider: anthropic             # anthropic | openai | azure_openai | gemini | ollama
  model: claude-opus-4-8
  api_key: ${ANTHROPIC_API_KEY}

agents:
  - name: assistant
    description: Front-line assistant
    prompt: prompts/assistant.md  # or inline `system:`
    skills: [house-style]
    mcp_servers: [tickets]

  - name: researcher
    system: You are a research specialist.

mcp:
  servers:
    - name: tickets
      transport: stdio            # or http (url: ...)
      command: npx
      args: ["-y", "my-mcp-server"]

peers:                            # remote agents reachable via call_next_agent
  - name: billing
    url: http://billing-agent:8000

auth:
  api_key: ${VFORGE_API_KEY}

server: { host: 0.0.0.0, port: 8000 }
```

Every agent automatically gets the `call_next_agent` tool when other agents or
peers exist — one agent can delegate to another without any custom code.

## Architecture

Strict layering; higher layers depend only on lower ones. The framework contains
**no business logic** — domains live in your MCP servers, prompts and skills.

```
CLI ─ Web console
      │
   Runtime (lifecycle, sessions, registry)
      │
   Orchestration (call_next_agent)
      │
   Agent Factory ── Agents (generic tool loop)
      │
   LLM Provider Layer  ·  MCP Manager  ·  Memory  ·  Skills  ·  RAG
      │
   A2A Transport (FastAPI)
      │
   Configuration Engine
```

See [docs/architecture.md](docs/architecture.md) for details.

## Documentation

Full documentation lives in [docs/](docs/index.md):

- [Getting Started](docs/getting-started.md) — first agent in five minutes
- [Developer Guide](docs/developer-guide.md) — prompts, skills, MCP tools, multi-agent, memory, RAG, auth
- [Configuration Reference](docs/configuration-reference.md) — every `application.yaml` key
- [API Reference](docs/api-reference.md) — HTTP endpoints (A2A + console) and the Python API
- [Extending VForge](docs/extending.md) — custom LLM providers, memory backends, tools
- [Deployment Guide](docs/deployment.md) — Docker, compose fleets, Kubernetes notes
- [Angular Console](webui/angular/README.md) — the bundled Angular UI and how to override it
- [Architecture](docs/architecture.md) — layers, startup sequence, the agent loop
- [Contributing](CONTRIBUTING.md) — working on the framework itself

## Development

```bash
pip install -e ".[dev]"
pytest                       # all tests run offline with a mock provider
```

Run the bundled example:

```bash
cd examples/assistant
export ANTHROPIC_API_KEY=...
vforge start
```

Docker:

```bash
docker build -f docker/Dockerfile -t assistant --build-arg APP_DIR=examples/assistant .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... assistant
```

## Extending

- **New LLM provider:** subclass `vforge.providers.llm.LLMProvider`, decorate with
  `@register_provider("name")`, reference it as `llm.provider: name`.
- **New memory backend:** subclass `vforge.providers.memory.MemoryProvider` and
  `@register_memory("name")`.
- **New tools:** write an MCP server in any language — the framework discovers and
  binds its tools automatically.

## License

MIT
