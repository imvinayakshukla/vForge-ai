"""Tracing tests: no-op when disabled, fail-fast when package missing."""

import importlib.util

import pytest

from vforge.config.models import OTelConfig
from vforge.observability.tracing import (
    TracingError,
    setup_tracing,
    shutdown_tracing,
    span,
    tracing_enabled,
)

OTEL_INSTALLED = importlib.util.find_spec("opentelemetry") is not None


def test_disabled_is_noop():
    setup_tracing(OTelConfig(enabled=False), "test-app")
    assert not tracing_enabled()
    with span("anything", foo="bar"):
        pass  # must not raise


def test_span_noop_propagates_exceptions():
    with pytest.raises(ValueError):
        with span("x"):
            raise ValueError("boom")


@pytest.mark.skipif(OTEL_INSTALLED, reason="opentelemetry installed; failure path untestable")
def test_enabled_without_package_fails_fast():
    with pytest.raises(TracingError, match=r"vforge\[otel\]"):
        setup_tracing(OTelConfig(enabled=True), "test-app")


@pytest.mark.skipif(not OTEL_INSTALLED, reason="requires vforge[otel]")
def test_enabled_creates_real_spans():
    try:
        setup_tracing(OTelConfig(enabled=True, console_export=False), "test-app")
        assert tracing_enabled()
        with span("unit.test", attr="value") as current:
            assert current is not None
    finally:
        shutdown_tracing()
    assert not tracing_enabled()
