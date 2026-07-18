"""Application runtime: startup, wiring and graceful shutdown.

``VForgeApp.bootstrap()`` performs the full startup sequence:

1. load + validate configuration
2. configure observability
3. connect MCP servers
4. build agents (factory injects LLM, tools, prompts, skills, memory)
5. attach orchestration (``call_next_agent``)
6. optionally start RAG and attach ``search_knowledge``
7. expose the runtime context to the transport layer
"""

from __future__ import annotations

import logging
from pathlib import Path

from vforge.agents.factory import AgentFactory
from vforge.config.loader import load_config
from vforge.config.models import VForgeConfig
from vforge.mcp.manager import MCPManager
from vforge.observability.logging import setup_logging
from vforge.observability.tracing import setup_tracing, shutdown_tracing
from vforge.orchestration.router import Orchestrator
from vforge.runtime.context import RuntimeContext
from vforge.skills.loader import SKILL_FILENAME, SKILLS_DIR

logger = logging.getLogger(__name__)


class VForgeApp:
    """Owns the lifecycle of a VForge application."""

    def __init__(self, app_dir: str | Path) -> None:
        self.app_dir = Path(app_dir).resolve()
        self.ctx: RuntimeContext | None = None
        self._factory: AgentFactory | None = None

    async def bootstrap(self, config: VForgeConfig | None = None) -> RuntimeContext:
        """Run the startup sequence and return the runtime context."""
        config = config or load_config(self.app_dir)
        setup_logging(config.observability.log_level, config.observability.json_logs)
        setup_tracing(config.observability.otel, config.app.name)
        logger.info("Starting VForge app '%s'", config.app.name)

        mcp = MCPManager(config.mcp_servers)
        await mcp.connect_all()

        factory = AgentFactory(config, self.app_dir, mcp)
        try:
            agents = factory.build_all()
        except Exception:
            await mcp.aclose()
            raise
        self._factory = factory

        orchestrator = Orchestrator(agents, config.peers)
        orchestrator.attach_to_agents()

        if config.rag.enabled:
            from vforge.rag.engine import RAGEngine

            rag = RAGEngine(config.rag, self.app_dir)
            await rag.index_documents()
            binding = rag.tool_binding()
            for agent in agents.values():
                agent.tools[binding.definition.name] = binding

        self.ctx = RuntimeContext(
            config=config,
            app_dir=self.app_dir,
            mcp=mcp,
            agents=agents,
            orchestrator=orchestrator,
            skills=self._collect_skills(config),
        )
        logger.info("VForge app '%s' ready", config.app.name)
        return self.ctx

    def _collect_skills(self, config: VForgeConfig) -> dict[str, dict]:
        """Index loaded skills for the console's Skill Viewer."""
        skills: dict[str, dict] = {}
        for agent_cfg in config.agents:
            for name in agent_cfg.skills:
                entry = skills.get(name)
                if entry is None:
                    path = self.app_dir / SKILLS_DIR / name / SKILL_FILENAME
                    entry = skills[name] = {
                        "content": path.read_text(encoding="utf-8").strip(),
                        "agents": [],
                    }
                entry["agents"].append(agent_cfg.name)
        return skills

    async def shutdown(self) -> None:
        """Release providers, memory backends and MCP connections."""
        if self.ctx is None:
            return
        logger.info("Shutting down VForge app '%s'", self.ctx.config.app.name)
        for agent in self.ctx.agents.values():
            try:
                await agent.memory.aclose()
            except Exception:  # pragma: no cover
                logger.debug("Error closing memory", exc_info=True)
        if self._factory:
            await self._factory.aclose()
        await self.ctx.mcp.aclose()
        shutdown_tracing()
        self.ctx = None


def serve(app_dir: str | Path) -> None:
    """Blocking entry point: bootstrap and run the HTTP server until stopped."""
    import asyncio

    import uvicorn

    from vforge.transport.a2a import create_app

    async def _main() -> None:
        vf = VForgeApp(app_dir)
        ctx = await vf.bootstrap()
        api = create_app(ctx)
        server_cfg = ctx.config.server
        server = uvicorn.Server(
            uvicorn.Config(api, host=server_cfg.host, port=server_cfg.port, log_config=None)
        )
        logger.info(
            "Serving '%s' on http://%s:%d (console at /, A2A at /a2a)",
            ctx.config.app.name, server_cfg.host, server_cfg.port,
        )
        try:
            await server.serve()  # handles SIGINT/SIGTERM gracefully
        finally:
            await vf.shutdown()

    asyncio.run(_main())
