"""MCP manager: connects configured servers at startup and pools clients."""

from __future__ import annotations

import asyncio
import logging

from vforge.config.models import MCPServerConfig
from vforge.mcp.client import MCPClient, MCPError, MCPTool

logger = logging.getLogger(__name__)


class MCPManager:
    """Owns one :class:`MCPClient` per configured server."""

    def __init__(self, servers: list[MCPServerConfig]) -> None:
        self._clients: dict[str, MCPClient] = {cfg.name: MCPClient(cfg) for cfg in servers}

    async def connect_all(self) -> None:
        """Connect every configured server concurrently. Fails fast."""
        if not self._clients:
            return
        results = await asyncio.gather(
            *(client.connect() for client in self._clients.values()), return_exceptions=True
        )
        failures = [
            f"{name}: {result}"
            for name, result in zip(self._clients, results)
            if isinstance(result, BaseException)
        ]
        if failures:
            await self.aclose()
            raise MCPError("Failed to connect MCP servers:\n" + "\n".join(failures))

    def client(self, name: str) -> MCPClient:
        try:
            return self._clients[name]
        except KeyError:
            raise MCPError(f"Unknown MCP server '{name}'") from None

    def tools_for(self, server_names: list[str]) -> list[MCPTool]:
        """Tools exposed by the given servers, in configuration order."""
        tools: list[MCPTool] = []
        for name in server_names:
            tools.extend(self.client(name).tools)
        return tools

    def all_tools(self) -> list[MCPTool]:
        return self.tools_for(list(self._clients))

    async def call_tool(self, server: str, tool: str, arguments: dict) -> str:
        return await self.client(server).call_tool(tool, arguments)

    async def aclose(self) -> None:
        await asyncio.gather(*(c.aclose() for c in self._clients.values()), return_exceptions=True)
