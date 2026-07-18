"""Runtime context: everything a running VForge application holds."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from vforge.agents.agent import Agent
from vforge.config.models import VForgeConfig
from vforge.mcp.manager import MCPManager
from vforge.orchestration.router import Orchestrator


@dataclass(slots=True)
class RuntimeContext:
    """Shared state injected into the transport layer and CLI."""

    config: VForgeConfig
    app_dir: Path
    mcp: MCPManager
    agents: dict[str, Agent] = field(default_factory=dict)
    orchestrator: Orchestrator | None = None
    skills: dict[str, dict] = field(default_factory=dict)
    """Loaded skills: name -> {"content": str, "agents": [agent names]}."""

    @property
    def default_agent(self) -> Agent:
        return next(iter(self.agents.values()))

    def agent(self, name: str) -> Agent:
        try:
            return self.agents[name]
        except KeyError:
            raise KeyError(f"Unknown agent '{name}'. Available: {sorted(self.agents)}") from None
