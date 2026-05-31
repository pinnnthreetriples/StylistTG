from __future__ import annotations

from typing import Any, ContextManager

class CollectorRegistry: ...

REGISTRY: CollectorRegistry

class _Metric:
    def labels(self, **labels: str) -> _Metric: ...
    def inc(self, amount: float = 1.0) -> None: ...
    def set(self, value: float) -> None: ...
    def observe(self, amount: float) -> None: ...
    def time(self) -> ContextManager[None]: ...

class Counter(_Metric):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = ...,
        *,
        registry: CollectorRegistry | None = ...,
    ) -> None: ...

class Gauge(_Metric):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = ...,
        *,
        registry: CollectorRegistry | None = ...,
    ) -> None: ...

class Histogram(_Metric):
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = ...,
        *,
        buckets: tuple[int, ...] | tuple[float, ...] = ...,
        registry: CollectorRegistry | None = ...,
    ) -> None: ...

def make_asgi_app(*, registry: CollectorRegistry | None = ...) -> Any: ...
