# Example: assistant

A two-agent VForge application: `assistant` answers directly and delegates
research to `researcher` via the built-in `call_next_agent` tool.

## Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
vforge start -d examples/assistant       # or `cd examples/assistant && vforge start`
```

Open http://localhost:8000 — the built-in console. Try:

> "Research the history of the metric system, then summarize it in two sentences."

and watch the delegation in the **Logs** tab and per-agent counters in
**Metrics**.

## Use the Angular console

```bash
cd webui/angular
npm install && npm run build
```

Then uncomment `server.ui_dir` in [application.yaml](application.yaml) and
restart. The Angular UI (same tabs, same API) replaces the built-in console at
`/`. See [webui/angular/README.md](../../webui/angular/README.md) for
customisation.

## Enable tracing

```bash
pip install "vforge[otel]"
docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one
```

Uncomment the `observability.otel` block in `application.yaml`, restart, chat,
then open http://localhost:16686 — you'll see `http.request → agent.run →
llm.complete / tool.execute` span trees per conversation turn.

## Add real tools

Uncomment the `mcp` block in `application.yaml` (requires Node.js for the demo
filesystem server) and add `mcp_servers: [fs]` to an agent, then inspect the
discovered tools with:

```bash
vforge list-tools -d examples/assistant
```
