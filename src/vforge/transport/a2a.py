"""A2A transport and developer console API.

Every running VForge app automatically exposes:

- ``GET  /.well-known/agent.json``  — A2A agent card (discovery)
- ``POST /a2a``                     — JSON-RPC ``message/send``
- ``GET  /health``                  — liveness/readiness
- ``GET  /``                        — developer web console
- ``/api/*``                        — console API (agents, chat, tools, …)
"""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from vforge import __version__
from vforge.auth.middleware import ApiKeyMiddleware
from vforge.observability.logging import (
    LOG_BUFFER,
    new_correlation_id,
    set_correlation_id,
)
from vforge.observability.metrics import metrics
from vforge.observability.tracing import span
from vforge.runtime.context import RuntimeContext

logger = logging.getLogger(__name__)

_START_TIME = time.time()
_CONSOLE_HTML = Path(__file__).parent.parent / "web" / "console.html"


class ChatRequest(BaseModel):
    agent: str | None = None
    message: str = Field(min_length=1)
    session_id: str = "default"


def create_app(ctx: RuntimeContext) -> FastAPI:
    """Build the FastAPI application for a runtime context."""
    app = FastAPI(title=ctx.config.app.name, version=__version__, docs_url="/api/docs")

    if ctx.config.auth.api_key:
        app.add_middleware(ApiKeyMiddleware, api_key=ctx.config.auth.api_key)

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or new_correlation_id()
        token = set_correlation_id(cid)
        try:
            with span(
                "http.request",
                **{
                    "http.method": request.method,
                    "http.path": request.url.path,
                    "correlation.id": cid,
                },
            ):
                response = await call_next(request)
        finally:
            set_correlation_id(None)  # reset for safety; token scope ends with request
            del token
        response.headers["X-Correlation-Id"] = cid
        return response

    # ------------------------------------------------------------------ A2A

    @app.get("/.well-known/agent.json")
    async def agent_card():
        return {
            "name": ctx.config.app.name,
            "description": ctx.config.app.description,
            "version": __version__,
            "url": "/a2a",
            "protocol": "a2a",
            "capabilities": {"streaming": False},
            "skills": [
                {"id": agent.name, "name": agent.name, "description": agent.description}
                for agent in ctx.agents.values()
            ],
        }

    @app.post("/a2a")
    async def a2a_endpoint(request: Request):
        try:
            body = await request.json()
        except Exception:
            return _rpc_error(None, -32700, "Parse error")

        rpc_id = body.get("id")
        if body.get("jsonrpc") != "2.0" or "method" not in body:
            return _rpc_error(rpc_id, -32600, "Invalid JSON-RPC request")

        method = body["method"]
        params = body.get("params", {})

        if method != "message/send":
            return _rpc_error(rpc_id, -32601, f"Method not found: {method}")

        message = params.get("message", {})
        text = "\n".join(
            part.get("text", "")
            for part in message.get("parts", [])
            if part.get("kind") == "text"
        ).strip()
        if not text:
            return _rpc_error(rpc_id, -32602, "message must contain at least one text part")

        agent_name = params.get("agent") or next(iter(ctx.agents))
        agent = ctx.agents.get(agent_name)
        if agent is None:
            return _rpc_error(rpc_id, -32602, f"Unknown agent '{agent_name}'")

        session_id = params.get("session_id") or f"a2a-{uuid.uuid4().hex[:8]}"
        metrics.increment("a2a.requests")
        try:
            answer = await agent.run(text, session_id=session_id)
        except Exception as exc:
            logger.exception("A2A request failed")
            return _rpc_error(rpc_id, -32000, f"Agent error: {exc}")

        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "role": "agent",
                    "parts": [{"kind": "text", "text": answer}],
                    "messageId": uuid.uuid4().hex,
                },
            }
        )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "app": ctx.config.app.name,
            "version": __version__,
            "uptime_seconds": round(time.time() - _START_TIME, 1),
            "agents": sorted(ctx.agents),
        }

    # ---------------------------------------------------------------- console
    #
    # UI resolution: when `server.ui_dir` is configured, that static build
    # (e.g. an Angular dist/) is served at "/" instead of the built-in
    # console. It is mounted after all routes, so /a2a, /health and /api/*
    # always take precedence. The console API stays available either way,
    # so custom UIs consume the same endpoints the built-in console does.

    custom_ui = _resolve_ui_dir(ctx)
    if custom_ui is None:

        @app.get("/", response_class=HTMLResponse)
        async def console():
            return _CONSOLE_HTML.read_text(encoding="utf-8")

    @app.get("/api/agents")
    async def api_agents():
        return [
            {
                "name": agent.name,
                "description": agent.description,
                "tools": sorted(agent.tools),
                "max_iterations": agent.max_iterations,
            }
            for agent in ctx.agents.values()
        ]

    @app.post("/api/chat")
    async def api_chat(payload: ChatRequest):
        agent = ctx.agents.get(payload.agent or next(iter(ctx.agents)))
        if agent is None:
            raise HTTPException(404, f"Unknown agent '{payload.agent}'")
        metrics.increment("console.chat_requests")
        try:
            answer = await agent.run(payload.message, session_id=payload.session_id)
        except Exception as exc:
            logger.exception("Console chat failed")
            raise HTTPException(500, str(exc)) from exc
        return {"agent": agent.name, "session_id": payload.session_id, "answer": answer}

    @app.get("/api/tools")
    async def api_tools():
        return [
            {
                "agent": agent.name,
                "name": binding.definition.name,
                "description": binding.definition.description,
                "input_schema": binding.definition.input_schema,
            }
            for agent in ctx.agents.values()
            for binding in agent.tools.values()
        ]

    @app.get("/api/prompts")
    async def api_prompts():
        return [
            {"agent": agent.name, "system_prompt": agent.system_prompt}
            for agent in ctx.agents.values()
        ]

    @app.get("/api/skills")
    async def api_skills():
        return [
            {"name": name, "agents": info["agents"], "content": info["content"]}
            for name, info in sorted(ctx.skills.items())
        ]

    @app.get("/api/sessions")
    async def api_sessions():
        result = []
        for agent in ctx.agents.values():
            for session_id in await agent.memory.sessions():
                history = await agent.memory.history(session_id)
                result.append(
                    {"agent": agent.name, "session_id": session_id, "messages": len(history)}
                )
        return result

    @app.get("/api/sessions/{agent_name}/{session_id}")
    async def api_session_detail(agent_name: str, session_id: str):
        agent = ctx.agents.get(agent_name)
        if agent is None:
            raise HTTPException(404, f"Unknown agent '{agent_name}'")
        history = await agent.memory.history(session_id)
        return [m.to_dict() for m in history]

    @app.get("/api/logs")
    async def api_logs():
        return list(LOG_BUFFER)

    @app.get("/api/metrics")
    async def api_metrics():
        return metrics.snapshot()

    @app.get("/api/config")
    async def api_config():
        redacted = ctx.config.model_dump()
        _redact_secrets(redacted)
        return redacted

    if custom_ui is not None:
        app.mount("/", StaticFiles(directory=custom_ui, html=True), name="custom-ui")
        logger.info("Serving custom UI from %s", custom_ui)

    return app


def _resolve_ui_dir(ctx: RuntimeContext) -> Path | None:
    """Resolve and validate ``server.ui_dir``; fail fast on a broken build."""
    ui_dir = ctx.config.server.ui_dir
    if not ui_dir:
        return None
    path = (ctx.app_dir / ui_dir).resolve()
    if not path.is_dir():
        raise RuntimeError(f"server.ui_dir does not exist: {path}")
    if not (path / "index.html").is_file():
        raise RuntimeError(
            f"server.ui_dir has no index.html: {path} — point it at the UI build output "
            f"(e.g. webui/angular's dist/vforge-console/browser)"
        )
    return path


def _rpc_error(rpc_id, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}},
        status_code=200,
    )


_SECRET_KEYS = {"api_key", "authorization", "token", "secret"}


def _redact_secrets(node) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _SECRET_KEYS and isinstance(value, str) and value:
                node[key] = "***"
            else:
                _redact_secrets(value)
    elif isinstance(node, list):
        for item in node:
            _redact_secrets(item)
