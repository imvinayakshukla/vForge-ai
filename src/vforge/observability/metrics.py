"""Lightweight in-process metrics.

Counters and duration histograms with no external dependency. Exposed via the
web console and ``GET /api/metrics``. Designed so an OpenTelemetry exporter can
be layered on later without changing call sites.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Iterator


class MetricsRegistry:
    """Thread-safe counters and timers keyed by name."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._durations: dict[str, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe(self, name: str, seconds: float) -> None:
        with self._lock:
            samples = self._durations[name]
            samples.append(seconds)
            if len(samples) > 1000:
                del samples[: len(samples) - 1000]

    @contextmanager
    def timer(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - start)

    def snapshot(self) -> dict:
        with self._lock:
            timers = {}
            for name, samples in self._durations.items():
                if samples:
                    timers[name] = {
                        "count": len(samples),
                        "avg_ms": round(sum(samples) / len(samples) * 1000, 2),
                        "max_ms": round(max(samples) * 1000, 2),
                    }
            return {"counters": dict(self._counters), "timers": timers}


metrics = MetricsRegistry()
"""Process-wide metrics registry."""
