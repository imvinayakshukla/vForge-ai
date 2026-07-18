# VForge Documentation

VForge is a configuration-driven framework for building AI agents. You supply
`application.yaml`, `prompts/` and `skills/`; the framework supplies the
runtime, LLM providers, MCP tool integration, agent-to-agent communication,
memory, observability, auth, a web console and a CLI.

## Contents

| Document | What it covers |
|---|---|
| [Getting Started](getting-started.md) | Install, scaffold, run your first agent in five minutes |
| [Developer Guide](developer-guide.md) | Building real agent applications: prompts, skills, tools, multi-agent, memory, RAG |
| [Configuration Reference](configuration-reference.md) | Every key in `application.yaml` |
| [API Reference](api-reference.md) | HTTP endpoints (A2A + console API) and the Python API |
| [Extending VForge](extending.md) | Custom LLM providers, memory backends and tools |
| [Deployment Guide](deployment.md) | Docker, environment variables, auth, running a fleet of agents |
| [Architecture](architecture.md) | Layers, design principles, startup sequence, the agent loop |
| [Contributing](../CONTRIBUTING.md) | Working on the framework itself |

## The 30-second mental model

```
application.yaml  ─┐
prompts/*.md      ─┼─▶  vforge start  ─▶  running agent app
skills/*/SKILL.md ─┘                        ├── web console      GET /
                                            ├── A2A endpoint     POST /a2a
                                            ├── agent card       GET /.well-known/agent.json
                                            └── health           GET /health
```

- An **agent** = a system prompt (+ skills) + an LLM provider + tools.
- **Tools** come from MCP servers, the built-in `call_next_agent`, and
  (optionally) RAG's `search_knowledge`. The framework never contains
  business logic — that lives in your prompts, skills and MCP servers.
- Agents talk to each other with `call_next_agent`: locally in-process,
  remotely over A2A (JSON-RPC).
