"""Structured logging with correlation IDs.

Every request handled by the A2A transport gets a correlation ID (taken from
the ``X-Correlation-Id`` header or generated). All log records emitted while
that request is being processed carry the ID, in both text and JSON formats.

A bounded in-memory ring buffer keeps recent log lines for the web console.
"""

from __future__ import annotations

import contextvars
import json
import logging
import uuid
from collections import deque
from datetime import datetime, timezone

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "vforge_correlation_id", default=None
)

# Ring buffer of recent formatted log lines, exposed via the web console.
LOG_BUFFER: deque[str] = deque(maxlen=500)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str | None) -> contextvars.Token:
    return _correlation_id.set(value)


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


class _CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get() or "-"
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            LOG_BUFFER.append(self.format(record))
        except Exception:  # pragma: no cover - never let logging break the app
            pass


def setup_logging(level: str = "INFO", json_logs: bool = False) -> None:
    """Configure root logging for the framework (idempotent)."""
    root = logging.getLogger()
    root.setLevel(level.upper())

    formatter: logging.Formatter
    if json_logs:
        formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)-7s [%(correlation_id)s] %(name)s: %(message)s"
        )

    # Replace previously-installed vforge handlers so setup is idempotent.
    for handler in list(root.handlers):
        if getattr(handler, "_vforge", False):
            root.removeHandler(handler)

    stream = logging.StreamHandler()
    buffer = _BufferHandler()
    for handler in (stream, buffer):
        handler.setFormatter(formatter)
        handler.addFilter(_CorrelationFilter())
        handler._vforge = True  # type: ignore[attr-defined]
        root.addHandler(handler)
