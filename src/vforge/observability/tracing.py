"""OpenTelemetry tracing (optional).

When ``observability.otel.enabled`` is true, VForge creates real OTel spans
for HTTP requests, agent runs, LLM calls and tool executions, exported over
OTLP/HTTP (and optionally to the console). Requires the ``vforge[otel]``
extra.

When disabled — the default — ``span()`` is a zero-cost no-op and the
OpenTelemetry packages are never imported.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, ContextManager

from vforge.config.models import OTelConfig

logger = logging.getLogger(__name__)


class TracingError(RuntimeError):
    """Raised when tracing is enabled but cannot be initialised."""


_tracer: Any | None = None
_provider: Any | None = None


def setup_tracing(config: OTelConfig, service_name: str) -> None:
    """Initialise the global tracer provider. No-op when tracing is disabled."""
    global _tracer, _provider
    if not config.enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise TracingError(
            "observability.otel.enabled is true but OpenTelemetry is not installed. "
            "Run: pip install 'vforge[otel]'"
        ) from exc

    resource = Resource.create({"service.name": config.service_name or service_name})
    provider = TracerProvider(resource=resource)

    if config.endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        except ImportError as exc:
            raise TracingError(
                "observability.otel.endpoint is set but the OTLP exporter is not installed. "
                "Run: pip install 'vforge[otel]'"
            ) from exc
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{config.endpoint.rstrip('/')}/v1/traces"))
        )
    if config.console_export:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    if not config.endpoint and not config.console_export:
        logger.warning(
            "OTel tracing enabled without 'endpoint' or 'console_export' — spans will be dropped"
        )

    trace.set_tracer_provider(provider)
    _provider = provider
    _tracer = trace.get_tracer("vforge")
    logger.info(
        "OpenTelemetry tracing enabled (service=%s, endpoint=%s)",
        config.service_name or service_name, config.endpoint,
    )


def shutdown_tracing() -> None:
    """Flush and shut down the tracer provider (idempotent)."""
    global _tracer, _provider
    if _provider is not None:
        try:
            _provider.shutdown()
        except Exception:  # pragma: no cover
            logger.debug("Error shutting down tracer provider", exc_info=True)
    _tracer = None
    _provider = None


def tracing_enabled() -> bool:
    return _tracer is not None


def span(name: str, **attributes: Any) -> ContextManager[Any]:
    """Open a span named *name*. A no-op context manager when tracing is off.

    Works in async code: OTel context propagation uses contextvars, so a span
    opened around ``await`` calls parents correctly.
    """
    if _tracer is None:
        return nullcontext()
    return _real_span(name, attributes)


@contextmanager
def _real_span(name: str, attributes: dict[str, Any]):
    from opentelemetry import trace

    with _tracer.start_as_current_span(name) as current:  # type: ignore[union-attr]
        for key, value in attributes.items():
            if value is not None:
                current.set_attribute(key, value)
        try:
            yield current
        except Exception as exc:
            current.record_exception(exc)
            current.set_status(trace.StatusCode.ERROR, str(exc))
            raise
