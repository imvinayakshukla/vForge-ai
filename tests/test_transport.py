"""A2A transport and console API tests (no network, mock provider)."""

import pytest
from fastapi.testclient import TestClient

from vforge.mcp.manager import MCPManager
from vforge.runtime.app import VForgeApp
from vforge.transport.a2a import create_app


@pytest.fixture
async def client(app_dir):
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    with TestClient(create_app(ctx)) as test_client:
        yield test_client
    await vf.shutdown()


async def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["agents"] == ["assistant", "helper"]


async def test_agent_card(client):
    body = client.get("/.well-known/agent.json").json()
    assert body["name"] == "test-app"
    assert {s["id"] for s in body["skills"]} == {"assistant", "helper"}


async def test_a2a_message_send(client):
    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{"kind": "text", "text": "ping"}]}},
    }
    body = client.post("/a2a", json=payload).json()
    assert body["result"]["parts"][0]["text"] == "echo: ping"


async def test_a2a_unknown_method(client):
    body = client.post(
        "/a2a", json={"jsonrpc": "2.0", "id": "1", "method": "bogus", "params": {}}
    ).json()
    assert body["error"]["code"] == -32601


async def test_console_chat_and_sessions(client):
    response = client.post(
        "/api/chat", json={"agent": "assistant", "message": "hi", "session_id": "s1"}
    )
    assert response.json()["answer"] == "echo: hi"
    sessions = client.get("/api/sessions").json()
    assert {"agent": "assistant", "session_id": "s1", "messages": 2} in sessions


async def test_config_endpoint_redacts_secrets(app_dir):
    (app_dir / "application.yaml").write_text(
        "app: {name: sec-app}\n"
        "llm: {provider: mock, api_key: super-secret}\n"
        "agents:\n  - {name: a, system: x}\n"
    )
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        with TestClient(create_app(ctx)) as test_client:
            config = test_client.get("/api/config").json()
            assert config["llm"]["api_key"] == "***"
    finally:
        await vf.shutdown()


async def test_auth_required_when_configured(app_dir):
    (app_dir / "application.yaml").write_text(
        "app: {name: auth-app}\n"
        "llm: {provider: mock}\n"
        "auth: {api_key: sekrit}\n"
        "agents:\n  - {name: a, system: x}\n"
    )
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        with TestClient(create_app(ctx)) as test_client:
            assert test_client.get("/health").status_code == 200  # public
            assert test_client.get("/api/agents").status_code == 401
            assert (
                test_client.get("/api/agents", headers={"X-API-Key": "sekrit"}).status_code == 200
            )
            assert (
                test_client.get(
                    "/api/agents", headers={"Authorization": "Bearer sekrit"}
                ).status_code
                == 200
            )
    finally:
        await vf.shutdown()


async def test_bootstrap_wires_orchestration(app_dir):
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        assert "call_next_agent" in ctx.agents["assistant"].tools
        assert isinstance(ctx.mcp, MCPManager)
        # skills were appended to the system prompt
        assert "Always greet politely." in ctx.agents["assistant"].system_prompt
    finally:
        await vf.shutdown()
