# Contributing to VForge

## Setup

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest          # entire suite runs offline via a mock provider (< 1s)
ruff check src tests
```

## Repository layout

```
src/vforge/
├── config/           # YAML loading, env interpolation, Pydantic models
├── providers/
│   ├── llm/          # neutral protocol + vendor adapters + registry
│   └── memory/       # memory backends + registry
├── mcp/              # MCP client (stdio + HTTP) and manager
├── agents/           # generic agent loop + factory
├── orchestration/    # call_next_agent routing (local + A2A peers)
├── transport/        # FastAPI app: A2A endpoints + console API
├── runtime/          # lifecycle (bootstrap/shutdown), runtime context
├── skills/           # SKILL.md loader
├── rag/              # optional Chroma retrieval
├── auth/             # API-key middleware
├── observability/    # logging, correlation IDs, metrics, optional OTel tracing
├── web/              # built-in console.html
└── cli/              # typer CLI
webui/angular/        # Angular console (optional replacement UI via server.ui_dir)
tests/                # pytest; no network, no real LLM calls
docs/                 # user-facing documentation
```

## Ground rules

1. **The framework stays generic.** No business domain knowledge (git, Jira,
   banking, …) in `src/vforge` — ever. Domain behaviour belongs in MCP
   servers, prompts and skills of *applications*.
2. **Layering is strict.** Higher layers depend on lower layers only
   (see `docs/architecture.md`); no circular imports.
3. **Async first.** All I/O is `async`; wrap unavoidable blocking work in
   `asyncio.to_thread`.
4. **Fail fast.** Configuration and wiring errors must surface at startup
   with actionable messages, not at request time.
5. **Extensibility over modification.** New providers/backends register via
   `register_provider` / `register_memory`; adding one must not change
   existing framework files.
6. **Type hints + docstrings** on every public class and function.
7. **Tests are offline.** Mock LLM providers (see `tests/conftest.py`);
   never call real APIs in the suite.

## Adding a feature

1. Open an issue describing the use case and the intended configuration
   surface (`application.yaml` first — code second).
2. Add or extend Pydantic models with validation and defaults
   (convention over configuration: most users should not need the new key).
3. Implement with tests and docstrings.
4. Update the relevant page under `docs/` and, if configuration changed,
   `docs/configuration-reference.md`.

## Pull requests

- Keep PRs focused; one concern per PR.
- `pytest` and `ruff check` must pass.
- Include a short rationale in the description: what problem, why this shape.

## Release checklist

- Bump `__version__` in `src/vforge/__init__.py` and `version` in
  `pyproject.toml`
- `pytest` green, docs updated, CHANGELOG entry
- Tag `vX.Y.Z`
