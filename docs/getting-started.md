# Getting Started

## Requirements

- Python **3.12+**
- An API key for at least one supported LLM provider
  (Anthropic, OpenAI, Azure OpenAI, Gemini) — or a local [Ollama](https://ollama.com) install, which needs no key.

## Install

VForge is a normal Python package — **agent projects depend on it; they never
contain or modify framework code.** Pick the install source that fits:

```bash
python3.12 -m venv .venv && source .venv/bin/activate

# a) from PyPI (once published)
pip install "vforge==0.1.0"

# b) straight from git, pinned to a tag
pip install "vforge @ git+https://github.com/you/vforge.git@v0.1.0"

# c) from a local checkout (framework development)
pip install -e /path/to/vforge            # add "[dev]" for tests, "[rag]", "[otel]" for extras
```

Check your environment:

```bash
vforge doctor
```

### How an agent project depends on VForge

Your agent app is just config + prompts + a dependency pin — its own
`pyproject.toml` (or `requirements.txt`) declares the framework version:

```toml
# my-agent/pyproject.toml
[project]
name = "my-agent"
version = "1.0.0"
dependencies = [
    "vforge==0.1.0",        # pin; bump deliberately when upgrading
]
```

```
my-agent/
├── pyproject.toml          # depends on vforge
├── application.yaml
├── prompts/
└── skills/
```

`pip install .` pulls the framework, and `vforge start` runs your app.
Upgrading the framework later = changing the version pin and re-testing —
your `application.yaml`, prompts and skills are untouched.

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
