"""Orchestration: the built-in ``call_next_agent`` tool.

Lets one agent delegate work to another. Routing is automatic:
- if the target is a local agent, it is invoked in-process
- if the target is a configured peer, the call goes over A2A (JSON-RPC)
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

import httpx

from vforge.agents.agent import ToolBinding
from vforge.config.models import PeerConfig
from vforge.providers.llm.base import ToolDef

if TYPE_CHECKING:
    from vforge.agents.agent import Agent

logger = logging.getLogger(__name__)

CALL_NEXT_AGENT = "call_next_agent"


class Orchestrator:
    """Routes agent-to-agent calls locally or over A2A."""

    def __init__(self, agents: dict[str, "Agent"], peers: list[PeerConfig]) -> None:
        self._agents = agents
        self._peers = {peer.name: peer for peer in peers}

    def known_targets(self, exclude: str) -> list[str]:
        local = [name for name in self._agents if name != exclude]
        return sorted(local + list(self._peers))

    async def dispatch(self, caller: str, target: str, message: str) -> str:
        if target == caller:
            return f"ERROR: agent '{caller}' cannot delegate to itself"
        if target in self._agents:
            logger.info("Orchestration: '%s' -> local agent '%s'", caller, target)
            # Delegated calls run in their own session so histories stay isolated.
            session_id = f"delegated-{caller}-{uuid.uuid4().hex[:8]}"
            return await self._agents[target].run(message, session_id=session_id)
        if target in self._peers:
            logger.info("Orchestration: '%s' -> peer '%s'", caller, target)
            return await self._call_peer(self._peers[target], message)
        return (
            f"ERROR: unknown agent '{target}'. "
            f"Available agents: {self.known_targets(exclude=caller)}"
        )

    async def _call_peer(self, peer: PeerConfig, message: str) -> str:
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": message}]}},
        }
        headers = {"Content-Type": "application/json"}
        if peer.api_key:
            headers["X-API-Key"] = peer.api_key
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{peer.url.rstrip('/')}/a2a", json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
        if "error" in body:
            return f"ERROR from peer '{peer.name}': {body['error'].get('message', body['error'])}"
        parts = body.get("result", {}).get("parts", [])
        return "\n".join(p.get("text", "") for p in parts if p.get("kind") == "text")

    def binding_for(self, agent_name: str) -> ToolBinding:
        """Build the ``call_next_agent`` tool for one agent."""
        targets = self.known_targets(exclude=agent_name)

        async def executor(arguments: dict) -> str:
            target = arguments.get("agent", "")
            message = arguments.get("message", "")
            if not target or not message:
                return "ERROR: call_next_agent requires 'agent' and 'message'"
            return await self.dispatch(agent_name, target, message)

        return ToolBinding(
            definition=ToolDef(
                name=CALL_NEXT_AGENT,
                description=(
                    "Delegate a task to another agent and get its answer. "
                    f"Available agents: {', '.join(targets) if targets else '(none)'}"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "agent": {
                            "type": "string",
                            "description": "Name of the agent to delegate to",
                            **({"enum": targets} if targets else {}),
                        },
                        "message": {
                            "type": "string",
                            "description": "The task or question to send to that agent",
                        },
                    },
                    "required": ["agent", "message"],
                },
            ),
            executor=executor,
        )

    def attach_to_agents(self) -> None:
        """Give every local agent the ``call_next_agent`` tool (when targets exist)."""
        for name, agent in self._agents.items():
            if self.known_targets(exclude=name):
                agent.tools[CALL_NEXT_AGENT] = self.binding_for(name)
