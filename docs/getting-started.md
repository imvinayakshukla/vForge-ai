# Getting Started

## Requirements

- Python **3.12+**
- An API key for at least one supported LLM provider
  (Anthropic, OpenAI, Azure OpenAI, Gemini) — or a local [Ollama](https://ollama.com) install, which needs no key.

## Install

From the framework repository:

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e .            # add ".[dev]" for tests, ".[rag]" for RAG
```

Check your environment:

```bash
vforge doctor
```

## Create your first agent

```bash
vforge scaffold my-agent
cd my-agent
```

This creates:

```
my-agent/
├── application.yaml            # the whole app, declaratively
├── prompts/
│   └── assistant.md            # the agent's system prompt
├── skills/
│   └── example-skill/
│       └── SKILL.md            # reusable prompt material
└── .env.example
```

Set your provider key and start:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
vforge start
```

Open **http://localhost:8000** — the developer console — and chat with your
agent. That's the whole loop: edit `application.yaml` or the prompt file,
restart, iterate.

## Validate without starting

```bash
vforge validate       # checks YAML, prompt files and skills; fails fast
```

## Talk to the agent over HTTP

The console is one client; anything that speaks JSON-RPC can be another:

```bash
curl -s http://localhost:8000/a2a \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {"role": "user", "parts": [{"kind": "text", "text": "Hello!"}]}
    }
  }'
```

The reply comes back as `result.parts[0].text`.

## Switch providers

Edit `application.yaml` — nothing else changes:

```yaml
llm:
  provider: ollama        # anthropic | openai | azure_openai | gemini | ollama
  model: llama3.1         # any model your Ollama install serves
```

## Next steps

- [Developer Guide](developer-guide.md) — add tools, more agents, skills, memory
- [Configuration Reference](configuration-reference.md) — everything `application.yaml` accepts
- [Deployment Guide](deployment.md) — Docker and production settings
