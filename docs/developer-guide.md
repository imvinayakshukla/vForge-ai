# Developer Guide

How to build real agent applications on VForge. Everything here is done in
`application.yaml`, `prompts/` and `skills/` — you never modify framework code.

## 1. Anatomy of an application

```
my-agent/
├── application.yaml     # configuration — the single source of truth
├── prompts/             # one .md file per agent system prompt
├── skills/              # skills/<name>/SKILL.md
└── docs-kb/             # (optional) documents for RAG
```

Run it with `vforge start` from that directory (or `vforge start -d path/`).

## 2. Prompts

An agent needs a system prompt, either from a file or inline:

```yaml
agents:
  - name: assistant
    prompt: prompts/assistant.md     # file, relative to the app directory
  - name: helper
    system: You are a terse helper.  # inline alternative
```

Missing prompt files are caught at startup (`vforge validate` catches them
too). Write prompts as plain Markdown; the entire file becomes the system
prompt.

**Tips**

- Describe the agent's job, boundaries and output style — not tool mechanics.
  Tool schemas are passed to the model separately.
- If the agent should delegate, say *when* to delegate (see §5); the
  `call_next_agent` tool itself is added automatically.

## 3. Skills

A skill is reusable prompt material — house style, domain glossaries, playbooks —
shared across agents and applications:

```
skills/
└── house-style/
    └── SKILL.md
```

```yaml
agents:
  - name: assistant
    prompt: prompts/assistant.md
    skills: [house-style, refund-policy]
```

Each listed skill's `SKILL.md` is appended to the agent's system prompt inside
a `<skill name="...">` block under a `# Skills` heading. A missing skill fails
startup.

## 4. Tools via MCP

Business capability belongs in [MCP](https://modelcontextprotocol.io) servers,
written in any language. VForge connects them at startup, discovers their
tools, and binds them to agents:

```yaml
mcp:
  servers:
    - name: fs
      transport: stdio
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "."]

    - name: tickets
      transport: http
      url: https://tickets.internal/mcp
      headers: { Authorization: "Bearer ${TICKETS_TOKEN}" }
      timeout: 30
      max_retries: 2

agents:
  - name: support
    prompt: prompts/support.md
    mcp_servers: [fs, tickets]      # which servers this agent may use
```

Behaviour:

- All servers are connected **concurrently at startup**; any failure aborts
  startup with a clear message (fail fast).
- Tool calls retry with backoff and reconnect automatically on transport
  failures (`max_retries` per server).
- A tool error is returned to the model as an `ERROR: ...` tool result so the
  agent can adapt — it does not crash the request.
- Inspect what a server exposes with `vforge list-tools`.

## 5. Multiple agents and delegation

Define several agents; every agent automatically receives the
`call_next_agent` tool whenever there is at least one other agent or peer:

```yaml
agents:
  - name: assistant
    prompt: prompts/assistant.md      # "delegate research to `researcher`"
  - name: researcher
    prompt: prompts/researcher.md
```

- **Local targets** run in-process; each delegated call gets its own session
  so histories stay isolated.
- **Remote targets** are declared under `peers` and reached over A2A:

```yaml
peers:
  - name: billing
    url: http://billing-agent:8000
    api_key: ${BILLING_API_KEY}       # sent as X-API-Key if the peer requires auth
```

The tool schema advertises the available target names to the model, so the
prompt only needs to say *when* to delegate, e.g.:

> When a question requires account or invoice data, delegate to the `billing`
> agent using `call_next_agent` and integrate its answer.

## 6. Per-agent LLM overrides

The global `llm` block is the default; any agent can override it entirely:

```yaml
llm:
  provider: anthropic
  model: claude-opus-4-8
  api_key: ${ANTHROPIC_API_KEY}

agents:
  - name: assistant
    prompt: prompts/assistant.md      # uses the global Anthropic config
  - name: classifier
    system: Classify the message as billing, technical or other. Reply with one word.
    llm:
      provider: ollama                # cheap local model for a cheap task
      model: llama3.1
```

## 7. Memory and sessions

Conversation history is stored per **session** per agent. Clients choose the
session:

- Console chat generates a session per browser tab.
- A2A callers pass `params.session_id` to continue a conversation.
- Delegated (`call_next_agent`) calls always get a fresh session.

```yaml
memory:
  provider: in_memory     # currently built in; see extending.md for custom backends
  max_messages: 200       # per-session cap; oldest turns are trimmed safely
```

Histories are visible in the console (**Sessions** tab) and via
`GET /api/sessions`.

## 8. RAG (optional)

Give agents a `search_knowledge` tool over your documents:

```bash
pip install "vforge[rag]"
```

```yaml
rag:
  enabled: true
  documents_dir: docs-kb          # indexed at startup (txt/md/rst/py/json/yaml/csv/html)
  persist_directory: .chroma      # omit for in-memory index
  chunk_size: 1000
  chunk_overlap: 100
  top_k: 4
```

Every agent gets the tool; results include `[source#chunk]` markers. The
framework runs identically with `rag.enabled: false` (the default) — chromadb
is only imported when enabled.

## 9. Auth

Protect `/a2a` and `/api/*` with an API key (health, agent card and the
console page stay public):

```yaml
auth:
  api_key: ${VFORGE_API_KEY}
```

Clients send `X-API-Key: <key>` or `Authorization: Bearer <key>`.

## 10. Observability

```yaml
observability:
  log_level: INFO
  json_logs: true        # structured JSON lines for log shippers
```

- Every HTTP request gets a correlation ID (honours incoming
  `X-Correlation-Id`, echoes it back) that appears on every log line.
- `GET /api/metrics` exposes counters and timings per agent and tool
  (`agent.<name>.requests`, `agent.<name>.llm_calls`, `tool.<name>.duration`, …).
- `GET /api/logs` returns the recent log ring buffer (also in the console).

## 11. Development workflow

```bash
vforge validate      # after every config/prompt edit
vforge doctor        # environment sanity (packages, keys, config)
vforge list-tools    # what your MCP servers actually expose
vforge start         # run; console at http://localhost:8000
```

The console's **Prompts** tab shows the *effective* system prompt (after
skills are appended) — useful when debugging behaviour.
