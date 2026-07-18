"""Observability: structured logging, correlation IDs and metrics."""

from vforge.observability.logging import (
    LOG_BUFFER,
    get_correlation_id,
    new_correlation_id,
    set_correlation_id,
    setup_logging,
)
from vforge.observability.metrics import MetricsRegistry, metrics
from vforge.observability.tracing import (
    TracingError,
    setup_tracing,
    shutdown_tracing,
    span,
    tracing_enabled,
)

__all__ = [
    "LOG_BUFFER",
    "MetricsRegistry",
    "TracingError",
    "get_correlation_id",
    "metrics",
    "new_correlation_id",
    "set_correlation_id",
    "setup_logging",
    "setup_tracing",
    "shutdown_tracing",
    "span",
    "tracing_enabled",
]
