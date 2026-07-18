"""``vforge`` CLI: start, validate, scaffold, list-tools, doctor, version."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer

from vforge import __version__

app = typer.Typer(
    name="vforge",
    help="VForge — build AI agents from application.yaml, prompts/ and skills/.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

DirOption = typer.Option(".", "--dir", "-d", help="Application directory (contains application.yaml)")


def _fail(message: str) -> None:
    typer.secho(f"✗ {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


@app.command()
def start(directory: str = DirOption) -> None:
    """Start the agent application (HTTP server, A2A endpoints, web console)."""
    from vforge.config.loader import ConfigError
    from vforge.runtime.app import serve

    try:
        serve(directory)
    except ConfigError as exc:
        _fail(str(exc))
    except KeyboardInterrupt:
        typer.echo("Stopped.")


@app.command()
def validate(directory: str = DirOption) -> None:
    """Validate application.yaml, prompt files and skills without starting."""
    from vforge.config.loader import ConfigError, load_config, read_system_prompt
    from vforge.skills.loader import SkillError, load_skills

    try:
        config = load_config(directory)
        for agent in config.agents:
            read_system_prompt(agent, Path(directory).resolve())
            load_skills(directory, agent.skills)
    except (ConfigError, SkillError) as exc:
        _fail(str(exc))
    typer.secho(
        f"✓ Configuration valid: app '{config.app.name}', "
        f"{len(config.agents)} agent(s), {len(config.mcp_servers)} MCP server(s)",
        fg=typer.colors.GREEN,
    )


@app.command()
def scaffold(
    name: str = typer.Argument(..., help="Name of the new agent application"),
    directory: str = typer.Option(".", "--dir", "-d", help="Parent directory"),
) -> None:
    """Create a new agent application skeleton."""
    target = Path(directory) / name
    if target.exists():
        _fail(f"Directory already exists: {target}")

    (target / "prompts").mkdir(parents=True)
    (target / "skills" / "example-skill").mkdir(parents=True)

    (target / "application.yaml").write_text(
        f"""app:
  name: {name}
  description: A VForge agent application

llm:
  provider: anthropic          # anthropic | openai | azure_openai | gemini | ollama
  model: claude-opus-4-8
  api_key: ${{ANTHROPIC_API_KEY}}
  max_tokens: 16000

agents:
  - name: assistant
    description: A helpful general-purpose assistant
    prompt: prompts/assistant.md
    skills:
      - example-skill
    # mcp_servers: [my-tools]

# mcp:
#   servers:
#     - name: my-tools
#       transport: stdio
#       command: npx
#       args: ["-y", "@modelcontextprotocol/server-filesystem", "."]

server:
  host: 0.0.0.0
  port: 8000

# auth:
#   api_key: ${{VFORGE_API_KEY}}
""",
        encoding="utf-8",
    )
    (target / "prompts" / "assistant.md").write_text(
        "You are a helpful assistant. Answer clearly and concisely.\n", encoding="utf-8"
    )
    (target / "skills" / "example-skill" / "SKILL.md").write_text(
        "# Example Skill\n\nWhen asked about VForge, explain that this app was scaffolded with "
        "`vforge scaffold` and is configured entirely through application.yaml.\n",
        encoding="utf-8",
    )
    (target / ".env.example").write_text("ANTHROPIC_API_KEY=sk-ant-...\n", encoding="utf-8")

    typer.secho(f"✓ Created {target}", fg=typer.colors.GREEN)
    typer.echo(f"  cd {target}\n  export ANTHROPIC_API_KEY=...\n  vforge start")


@app.command(name="list-tools")
def list_tools(directory: str = DirOption) -> None:
    """Connect configured MCP servers and list every discovered tool."""
    from vforge.config.loader import ConfigError, load_config
    from vforge.mcp.manager import MCPManager

    try:
        config = load_config(directory)
    except ConfigError as exc:
        _fail(str(exc))
        return

    async def _run() -> None:
        manager = MCPManager(config.mcp_servers)
        try:
            await manager.connect_all()
            tools = manager.all_tools()
            if not tools:
                typer.echo("No MCP tools found (no servers configured?).")
            for tool in tools:
                typer.echo(f"[{tool.server}] {tool.name} — {tool.description}")
        finally:
            await manager.aclose()

    try:
        asyncio.run(_run())
    except Exception as exc:
        _fail(str(exc))


@app.command()
def doctor(directory: str = DirOption) -> None:
    """Diagnose the environment and configuration."""
    from vforge.config.loader import ConfigError, load_config

    ok = True

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and passed
        mark = typer.style("✓", fg=typer.colors.GREEN) if passed else typer.style("✗", fg=typer.colors.RED)
        typer.echo(f" {mark} {label}" + (f" — {detail}" if detail else ""))

    typer.echo(f"VForge {__version__} doctor\n")
    check("Python >= 3.12", sys.version_info >= (3, 12), sys.version.split()[0])

    for package in ("pydantic", "yaml", "fastapi", "uvicorn", "httpx", "anthropic", "openai"):
        try:
            __import__(package)
            check(f"package '{package}'", True)
        except ImportError:
            check(f"package '{package}'", False, "not installed")

    config_path = Path(directory) / "application.yaml"
    check("application.yaml present", config_path.is_file(), str(config_path))
    if config_path.is_file():
        try:
            config = load_config(directory)
            check("configuration valid", True, f"{len(config.agents)} agent(s)")
            provider = config.llm.provider
            env_hint = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "azure_openai": "AZURE_OPENAI_API_KEY",
                "gemini": "GEMINI_API_KEY",
            }.get(provider)
            if env_hint and not (config.llm.api_key or os.environ.get(env_hint)):
                check(f"API key for provider '{provider}'", False, f"set {env_hint} or llm.api_key")
            else:
                check(f"API key for provider '{provider}'", True)
        except ConfigError as exc:
            check("configuration valid", False, str(exc).splitlines()[0])

    raise typer.Exit(code=0 if ok else 1)


@app.command()
def version() -> None:
    """Print the VForge version."""
    typer.echo(f"vforge {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
