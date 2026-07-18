"""Configuration engine tests: env resolution, validation, fail-fast."""

import pytest

from vforge.config.loader import ConfigError, load_config
from vforge.utils.env import MissingEnvVarError, resolve_env


class TestEnvResolution:
    def test_resolves_set_variable(self, monkeypatch):
        monkeypatch.setenv("MY_KEY", "secret")
        assert resolve_env({"api_key": "${MY_KEY}"}) == {"api_key": "secret"}

    def test_default_used_when_unset(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        assert resolve_env("${MISSING_VAR:fallback}") == "fallback"

    def test_missing_without_default_raises(self, monkeypatch):
        monkeypatch.delenv("MISSING_VAR", raising=False)
        with pytest.raises(MissingEnvVarError):
            resolve_env("${MISSING_VAR}")

    def test_nested_structures(self, monkeypatch):
        monkeypatch.setenv("PORT", "9000")
        data = {"servers": [{"port": "prefix-${PORT}"}]}
        assert resolve_env(data) == {"servers": [{"port": "prefix-9000"}]}


class TestLoadConfig:
    def test_valid_config_loads(self, app_dir):
        config = load_config(app_dir)
        assert config.app.name == "test-app"
        assert [a.name for a in config.agents] == ["assistant", "helper"]

    def test_missing_file_fails(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_config(tmp_path)

    def test_missing_prompt_file_fails(self, app_dir):
        (app_dir / "prompts" / "assistant.md").unlink()
        with pytest.raises(ConfigError, match="prompt file not found"):
            load_config(app_dir)

    def test_agent_without_prompt_or_system_fails(self, app_dir):
        (app_dir / "application.yaml").write_text(
            "llm: {provider: mock}\nagents:\n  - name: broken\n"
        )
        with pytest.raises(ConfigError, match="prompt.*or 'system'"):
            load_config(app_dir)

    def test_duplicate_agent_names_fail(self, app_dir):
        (app_dir / "application.yaml").write_text(
            "agents:\n"
            "  - {name: a, system: x}\n"
            "  - {name: a, system: y}\n"
        )
        with pytest.raises(ConfigError, match="Duplicate agent names"):
            load_config(app_dir)

    def test_unknown_mcp_server_reference_fails(self, app_dir):
        (app_dir / "application.yaml").write_text(
            "agents:\n  - {name: a, system: x, mcp_servers: [ghost]}\n"
        )
        with pytest.raises(ConfigError, match="unknown MCP servers"):
            load_config(app_dir)

    def test_unknown_top_level_key_fails(self, app_dir):
        (app_dir / "application.yaml").write_text(
            "agents:\n  - {name: a, system: x}\ntypo_key: true\n"
        )
        with pytest.raises(ConfigError):
            load_config(app_dir)

    def test_stdio_server_requires_command(self, app_dir):
        (app_dir / "application.yaml").write_text(
            "agents:\n  - {name: a, system: x}\n"
            "mcp:\n  servers:\n    - {name: s, transport: stdio}\n"
        )
        with pytest.raises(ConfigError, match="requires 'command'"):
            load_config(app_dir)
