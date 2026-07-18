"""Minimal MCP (Model Context Protocol) client.

Implements the subset of MCP the framework needs — ``initialize``,
``tools/list`` and ``tools/call`` — over two transports:

- **stdio**: newline-delimited JSON-RPC to a spawned subprocess
- **http**: Streamable HTTP (JSON-RPC POST, JSON or SSE responses,
  ``Mcp-Session-Id`` header propagation)

Business tools live in MCP servers; the framework only transports calls.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from vforge.config.models import MCPServerConfig
from vforge.observability.tracing import span

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2025-03-26"


class MCPError(RuntimeError):
    """Raised for MCP transport or protocol failures."""


@dataclass(slots=True)
class MCPTool:
    """A tool discovered on an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server: str


class MCPTransport(ABC):
    """A JSON-RPC request/response channel to one MCP server."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...

    @abstractmethod
    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    async def aclose(self) -> None: ...


class StdioTransport(MCPTransport):
    """Newline-delimited JSON-RPC over a child process's stdio."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._process: asyncio.subprocess.Process | None = None
        self._reader_task: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._ids = itertools.count(1)

    async def start(self) -> None:
        env = {**os.environ, **self._config.env}
        self._process = await asyncio.create_subprocess_exec(
            self._config.command,  # validated non-null for stdio transport
            *self._config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        self._reader_task = asyncio.create_task(self._read_loop(), name=f"mcp-{self._config.name}")

    async def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        try:
            while True:
                line = await self._process.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("MCP %s: ignoring non-JSON stdout line", self._config.name)
                    continue
                msg_id = payload.get("id")
                future = self._pending.pop(msg_id, None) if msg_id is not None else None
                if future and not future.done():
                    future.set_result(payload)
        finally:
            error = MCPError(f"MCP server '{self._config.name}' closed its stdio stream")
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(error)
            self._pending.clear()

    async def _send(self, payload: dict[str, Any]) -> None:
        if not self._process or self._process.returncode is not None or not self._process.stdin:
            raise MCPError(f"MCP server '{self._config.name}' is not running")
        self._process.stdin.write(json.dumps(payload).encode() + b"\n")
        await self._process.stdin.drain()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg_id = next(self._ids)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = future
        await self._send({"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}})
        try:
            response = await asyncio.wait_for(future, timeout=self._config.timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(msg_id, None)
            raise MCPError(
                f"MCP server '{self._config.name}': '{method}' timed out after {self._config.timeout}s"
            ) from exc
        if "error" in response:
            raise MCPError(f"MCP server '{self._config.name}': {response['error']}")
        return response.get("result", {})

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def aclose(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()


class HTTPTransport(MCPTransport):
    """MCP Streamable HTTP transport."""

    def __init__(self, config: MCPServerConfig) -> None:
        self._config = config
        self._client: httpx.AsyncClient | None = None
        self._session_id: str | None = None
        self._ids = itertools.count(1)

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=self._config.timeout)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self._config.headers,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        if not self._client:
            raise MCPError(f"MCP server '{self._config.name}' transport not started")
        assert self._config.url is not None
        try:
            response = await self._client.post(self._config.url, json=payload, headers=self._headers())
        except httpx.HTTPError as exc:
            raise MCPError(f"MCP server '{self._config.name}': HTTP error: {exc}") from exc
        if response.status_code >= 400:
            raise MCPError(
                f"MCP server '{self._config.name}': HTTP {response.status_code}: {response.text[:300]}"
            )
        if session := response.headers.get("mcp-session-id"):
            self._session_id = session
        return response

    async def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg_id = next(self._ids)
        payload = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {}}
        response = await self._post(payload)

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            message = _parse_sse_response(response.text, msg_id)
        else:
            message = response.json()
        if message is None:
            raise MCPError(f"MCP server '{self._config.name}': no response for '{method}'")
        if "error" in message:
            raise MCPError(f"MCP server '{self._config.name}': {message['error']}")
        return message.get("result", {})

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._post({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def aclose(self) -> None:
        if self._client:
            await self._client.aclose()


def _parse_sse_response(body: str, msg_id: int) -> dict[str, Any] | None:
    """Extract the JSON-RPC response with *msg_id* from an SSE body."""
    for chunk in body.split("\n\n"):
        data_lines = [line[5:].strip() for line in chunk.splitlines() if line.startswith("data:")]
        if not data_lines:
            continue
        try:
            message = json.loads("\n".join(data_lines))
        except json.JSONDecodeError:
            continue
        if message.get("id") == msg_id:
            return message
    return None


class MCPClient:
    """One connected MCP server: handshake, discovery, tool execution, retries."""

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.tools: list[MCPTool] = []
        self._transport: MCPTransport | None = None
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self.config.name

    async def connect(self) -> None:
        """Start the transport, run the MCP handshake and discover tools."""
        transport: MCPTransport
        if self.config.transport == "stdio":
            transport = StdioTransport(self.config)
        else:
            transport = HTTPTransport(self.config)
        await transport.start()

        try:
            await transport.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "vforge", "version": "0.1.0"},
                },
            )
            await transport.notify("notifications/initialized")
            result = await transport.request("tools/list")
        except Exception:
            await transport.aclose()
            raise

        self._transport = transport
        self.tools = [
            MCPTool(
                name=tool["name"],
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {"type": "object", "properties": {}}),
                server=self.name,
            )
            for tool in result.get("tools", [])
        ]
        logger.info("MCP server '%s' connected (%d tools)", self.name, len(self.tools))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool, retrying (with one reconnect) on transport failures."""
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                if self._transport is None:
                    async with self._lock:
                        if self._transport is None:
                            await self.connect()
                assert self._transport is not None
                with span(
                    "mcp.call_tool",
                    **{"mcp.server": self.name, "mcp.tool": name, "retry.attempt": attempt},
                ):
                    result = await self._transport.request(
                        "tools/call", {"name": name, "arguments": arguments}
                    )
                return _render_tool_result(result)
            except MCPError as exc:
                last_error = exc
                logger.warning(
                    "MCP tool '%s' on '%s' failed (attempt %d/%d): %s",
                    name, self.name, attempt + 1, self.config.max_retries + 1, exc,
                )
                await self._reset()
                await asyncio.sleep(min(2**attempt * 0.2, 2.0))
        raise MCPError(f"Tool '{name}' on server '{self.name}' failed: {last_error}")

    async def _reset(self) -> None:
        async with self._lock:
            if self._transport:
                await self._transport.aclose()
                self._transport = None

    async def aclose(self) -> None:
        await self._reset()


def _render_tool_result(result: dict[str, Any]) -> str:
    """Flatten an MCP tool result into text for the model."""
    parts: list[str] = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        else:
            parts.append(json.dumps(block))
    text = "\n".join(parts) if parts else json.dumps(result)
    if result.get("isError"):
        return f"ERROR: {text}"
    return text
