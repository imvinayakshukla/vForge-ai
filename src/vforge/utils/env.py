"""Environment variable interpolation for configuration values.

Supports ``${VAR}`` and ``${VAR:default}`` placeholders anywhere inside
strings loaded from ``application.yaml``. Interpolation is applied
recursively to dicts, lists and strings.
"""

from __future__ import annotations

import os
import re
from typing import Any

_PLACEHOLDER = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")


class MissingEnvVarError(RuntimeError):
    """Raised when a referenced environment variable is not set and has no default."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"Environment variable '{name}' is referenced in configuration but is not set "
            f"and no default was provided (use ${{{name}:default}} to supply one)."
        )
        self.name = name


def _substitute(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        resolved = os.environ.get(name)
        if resolved is not None:
            return resolved
        if default is not None:
            return default
        raise MissingEnvVarError(name)

    return _PLACEHOLDER.sub(replace, value)


def resolve_env(data: Any) -> Any:
    """Recursively resolve ``${VAR}`` placeholders in *data*."""
    if isinstance(data, str):
        return _substitute(data)
    if isinstance(data, dict):
        return {key: resolve_env(value) for key, value in data.items()}
    if isinstance(data, list):
        return [resolve_env(item) for item in data]
    return data
