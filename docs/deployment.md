# Deployment Guide

## Environment variables

Configuration references secrets with `${VAR}` placeholders — the process
environment is the single secret store. Typical set:

| Variable | Used by |
|---|---|
| `ANTHROPIC_API_KEY` | `llm.provider: anthropic` |
| `OPENAI_API_KEY` | `llm.provider: openai` |
| `AZURE_OPENAI_API_KEY` | `llm.provider: azure_openai` |
| `GEMINI_API_KEY` | `llm.provider: gemini` |
| `VFORGE_API_KEY` | `auth.api_key` (protects `/a2a` and `/api`) |

Never commit real keys; keep an `.env.example` in the repo and inject real
values at deploy time (container env, secret manager).

## Production checklist

- **Enable auth**: set `auth.api_key: ${VFORGE_API_KEY}` — otherwise anyone
  who can reach the port can drive your agents (and spend your tokens).
- **JSON logs**: `observability: { json_logs: true }` for log shippers.
- **Put TLS in front**: run behind a reverse proxy / ingress; VForge serves
  plain HTTP.
- **Health checks**: point liveness/readiness probes at `GET /health`.
- **Bound the loop**: review `agents[].max_iterations` and `llm.max_tokens`
  for cost control.
- **Pin versions**: install the framework from a locked requirements file or
  image digest.

## Docker

The repo ships a generic Dockerfile that bakes the framework plus one
application directory:

```bash
docker build -f docker/Dockerfile -t my-agent \
  --build-arg APP_DIR=examples/assistant .

docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e VFORGE_API_KEY=change-me \
  my-agent
```

The image runs `vforge start` in the app directory; config changes are a
rebuild (or mount your app dir as a volume during development:
`-v $PWD/my-agent:/app`).

## docker-compose: a two-agent fleet

Each agent app is its own container; they find each other through `peers`:

```yaml
# docker-compose.yaml
services:
  assistant:
    build: { context: ., dockerfile: docker/Dockerfile, args: { APP_DIR: apps/assistant } }
    ports: ["8000:8000"]
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      BILLING_URL: http://billing:8000

  billing:
    build: { context: ., dockerfile: docker/Dockerfile, args: { APP_DIR: apps/billing } }
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
```

```yaml
# apps/assistant/application.yaml (excerpt)
peers:
  - name: billing
    url: ${BILLING_URL:http://localhost:8001}
```

The assistant's model can now `call_next_agent` → `billing`; the call travels
over A2A JSON-RPC between containers.

## Kubernetes notes

A minimal Deployment needs nothing framework-specific:

- container port `8000`; liveness + readiness probes on `/health`
- secrets injected as env vars (`ANTHROPIC_API_KEY`, `VFORGE_API_KEY`, …)
- one Service per agent app; peer URLs point at Service DNS names
- MCP stdio servers run *inside* the same container (they are spawned as
  subprocesses); HTTP MCP servers can be separate Services

Graceful shutdown is built in: SIGTERM → uvicorn drains → memory backends,
LLM providers and MCP connections are closed in order.

## Scaling considerations

- The default `in_memory` memory provider is **per-process**: with multiple
  replicas, pin sessions to replicas (sticky routing) or implement a shared
  backend (see [Extending VForge](extending.md) — Redis fits naturally).
- Metrics and the log buffer are also per-process; scrape `/api/metrics` per
  pod or attach your own exporter.
- Agent workloads are I/O-bound (LLM + tool calls); a single process handles
  many concurrent sessions — scale out for redundancy first, throughput second.
