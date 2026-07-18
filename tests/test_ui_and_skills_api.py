"""Skill viewer API and custom-UI override tests."""

import pytest
from fastapi.testclient import TestClient

from vforge.runtime.app import VForgeApp
from vforge.transport.a2a import create_app


async def test_skills_endpoint(app_dir):
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        with TestClient(create_app(ctx)) as client:
            skills = client.get("/api/skills").json()
        assert skills == [
            {"name": "greeting", "agents": ["assistant"], "content": "Always greet politely."}
        ]
    finally:
        await vf.shutdown()


async def test_custom_ui_served_when_configured(app_dir):
    ui = app_dir / "dist"
    ui.mkdir()
    (ui / "index.html").write_text("<html><body>CUSTOM UI</body></html>")
    (ui / "main.js").write_text("console.log('custom')")
    config_text = (app_dir / "application.yaml").read_text()
    (app_dir / "application.yaml").write_text(config_text + "\nserver:\n  ui_dir: dist\n")

    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        with TestClient(create_app(ctx)) as client:
            assert "CUSTOM UI" in client.get("/").text
            assert client.get("/main.js").status_code == 200
            # API routes still win over the static mount
            assert client.get("/health").json()["status"] == "ok"
            assert client.get("/api/agents").status_code == 200
    finally:
        await vf.shutdown()


async def test_missing_ui_dir_fails_fast(app_dir):
    config_text = (app_dir / "application.yaml").read_text()
    (app_dir / "application.yaml").write_text(config_text + "\nserver:\n  ui_dir: nope\n")
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        with pytest.raises(RuntimeError, match="ui_dir does not exist"):
            create_app(ctx)
    finally:
        await vf.shutdown()


async def test_ui_assets_public_with_auth(app_dir):
    ui = app_dir / "dist"
    ui.mkdir()
    (ui / "index.html").write_text("<html>UI</html>")
    config_text = (app_dir / "application.yaml").read_text()
    (app_dir / "application.yaml").write_text(
        config_text + "\nserver:\n  ui_dir: dist\nauth:\n  api_key: sekrit\n"
    )
    vf = VForgeApp(app_dir)
    ctx = await vf.bootstrap()
    try:
        with TestClient(create_app(ctx)) as client:
            assert client.get("/").status_code == 200          # UI public
            assert client.get("/api/skills").status_code == 401  # API protected
    finally:
        await vf.shutdown()
