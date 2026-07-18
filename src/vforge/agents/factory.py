"""Agent factory: builds agents from configuration, injecting everything.

Developers never instantiate agents manually. The factory wires together:
LLM provider, MCP tools, prompt file, skills, memory, orchestration tools and
(optionally) RAG retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vforge.agents.agent import Agent, ToolBinding
from vforge.config.loader import read_system_prompt
from vforge.config.models import VForgeConfig
from vforge.mcp.manager import MCPManager
from vforge.providers.llm.base import LLMProvider, ToolDef, create_provider
from vforge.providers.memory.base import create_memory
from vforge.skills.loader import apply_skills, load_skills

logger = logging.getLogger(__name__)


class AgentFactory:
    """Creates fully wired :class:`Agent` instances from a :class:`VForgeConfig`."""

    def __init__(self, config: VForgeConfig, app_dir: Path, mcp: MCPManager) -> None:
        self._config = config
        self._app_dir = app_dir
        self._mcp = mcp
        self._providers: list[LLMProvider] = []

    def build_all(self) -> dict[str, Agent]:
        agents = {cfg.name: self._build(cfg) for cfg in self._config.agents}
        logger.info("Built %d agent(s): %s", len(agents), ", ".join(agents))
        return agents

    def _build(self, agent_cfg) -> Agent:
        # System prompt: prompt file or inline, plus skills.
        system_prompt = read_system_prompt(agent_cfg, self._app_dir)
        skills_block = load_skills(self._app_dir, agent_cfg.skills)
        system_prompt = apply_skills(system_prompt, skills_block)

        # LLM provider: per-agent override merged over the global config.
        llm_cfg = agent_cfg.llm or self._config.llm
        provider = create_provider(llm_cfg)
        self._providers.append(provider)

        memory = create_memory(agent_cfg.memory or self._config.memory)

        tools: dict[str, ToolBinding] = {}
        for mcp_tool in self._mcp.tools_for(agent_cfg.mcp_servers):
            if mcp_tool.name in tools:
                logger.warning(
                    "Agent '%s': duplicate tool name '%s' (server '%s' shadowed)",
                    agent_cfg.name, mcp_tool.name, mcp_tool.server,
                )
                continue
            tools[mcp_tool.name] = self._bind_mcp_tool(mcp_tool)

        return Agent(
            name=agent_cfg.name,
            description=agent_cfg.description,
            system_prompt=system_prompt,
            provider=provider,
            memory=memory,
            tools=tools,
            max_iterations=agent_cfg.max_iterations,
        )

    def _bind_mcp_tool(self, mcp_tool) -> ToolBinding:
        server, name = mcp_tool.server, mcp_tool.name

        async def executor(arguments: dict) -> str:
            return await self._mcp.call_tool(server, name, arguments)

        return ToolBinding(
            definition=ToolDef(
                name=name, description=mcp_tool.description, input_schema=mcp_tool.input_schema
            ),
            executor=executor,
        )

    async def aclose(self) -> None:
        for provider in self._providers:
            try:
                await provider.aclose()
            except Exception:  # pragma: no cover
                logger.debug("Error closing provider", exc_info=True)
