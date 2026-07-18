"""Load and validate ``application.yaml``.

Responsibilities:
- parse YAML
- resolve ``${VAR}`` environment placeholders
- resolve prompt files referenced by agents
- validate with Pydantic and fail fast with readable errors
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from vforge.config.models import AgentConfig, VForgeConfig
from vforge.utils.env import resolve_env

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "application.yaml"


class ConfigError(RuntimeError):
    """Raised for any configuration problem. Message is user-facing."""


def load_config(app_dir: str | Path, filename: str = CONFIG_FILENAME) -> VForgeConfig:
    """Load, interpolate and validate the configuration in *app_dir*."""
    app_dir = Path(app_dir).resolve()
    config_path = app_dir / filename
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path} must contain a YAML mapping at the top level")

    raw = resolve_env(raw)

    try:
        config = VForgeConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration in {config_path}:\n{exc}") from exc

    _check_prompt_files(config, app_dir)
    logger.info("Loaded configuration for app '%s' (%d agents)", config.app.name, len(config.agents))
    return config


def _check_prompt_files(config: VForgeConfig, app_dir: Path) -> None:
    """Fail fast if any referenced prompt file is missing."""
    for agent in config.agents:
        if agent.prompt:
            path = app_dir / agent.prompt
            if not path.is_file():
                raise ConfigError(
                    f"Agent '{agent.name}': prompt file not found: {path}"
                )


def read_system_prompt(agent: AgentConfig, app_dir: Path) -> str:
    """Return the system prompt for *agent*, reading its prompt file if configured."""
    if agent.system:
        return agent.system
    assert agent.prompt is not None  # guaranteed by AgentConfig validation
    return (app_dir / agent.prompt).read_text(encoding="utf-8").strip()
