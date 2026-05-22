from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
import hashlib
from typing import Any, ContextManager, Literal

import app.platform_bootstrap  # noqa: F401

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, REGISTRY
except ImportError:  # pragma: no cover - keeps OpenAPI export importable before deps sync.
    CollectorRegistry = Any  # type: ignore[misc, assignment]
    Counter = Gauge = Histogram = None  # type: ignore[assignment]
    REGISTRY = None

from app.config import settings


ReserveOutcome = Literal["RESERVED", "STALE", "BLOCKED", "WARNING", "RATE_BLOCKED"]
TypingOutcome = Literal["success", "error", "timeout", "skipped"]
OverloadSeverity = Literal["warning", "blocked"]
AttemptResolution = Literal["sent", "failed", "skipped"]


class SafetyMetrics:
    """Prometheus metrics for safety-pipeline SLI/SLO monitoring."""

    def __init__(
        self,
        *,
        registry: CollectorRegistry = REGISTRY,
        enabled: bool | None = None,
    ) -> None:
        self.registry = registry
        self.enabled = (
            settings.metrics_enabled if enabled is None else enabled
        ) and REGISTRY is not None
        if not self.enabled:
            return

        self._gate_blocks = Counter(
            "safety_gate_blocks_total",
            "Safety gate blocked verdicts by workspace, intent, and reason.",
            ("workspace_id", "intent", "reason"),
            registry=registry,
        )
        self._gate_evaluate_duration = Histogram(
            "safety_gate_evaluate_duration_seconds",
            "Safety gate evaluation latency.",
            ("intent", "cache_hit"),
            registry=registry,
        )
        self._quarantine_active = Gauge(
            "quarantine_active",
            "Active account quarantines by workspace and reason.",
            ("workspace_id", "reason"),
            registry=registry,
        )
        self._account_total = Gauge(
            "account_total",
            "Total accounts by workspace for safety SLO denominators.",
            ("workspace_id",),
            registry=registry,
        )
        self._quarantine_opened = Counter(
            "quarantine_opened_total",
            "Opened account quarantines by workspace and reason.",
            ("workspace_id", "reason"),
            registry=registry,
        )
        self._quarantine_released = Counter(
            "quarantine_released_total",
            "Released account quarantines by workspace, reason, and release mode.",
            ("workspace_id", "reason", "mode"),
            registry=registry,
        )
        self._ggr_score = Histogram(
            "ggr_score",
            "GGR account survivability score.",
            ("workspace_id", "bucket"),
            buckets=(1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
            registry=registry,
        )
        self._flood_wait = Counter(
            "flood_wait_total",
            "Observed Telegram FLOOD_WAIT events by workspace and account hash.",
            ("workspace_id", "account_id_hash"),
            registry=registry,
        )
        self._attempt_send_duration = Histogram(
            "attempt_send_duration_seconds",
            "Telegram send attempt duration by strategy.",
            ("strategy",),
            registry=registry,
        )
        self._reserve_outcomes = Counter(
            "safety_gate_reserve_outcomes_total",
            "Safety gate reserve outcomes.",
            ("outcome",),
            registry=registry,
        )
        self._typing_emit = Counter(
            "human_behavior_typing_emit_total",
            "Human behavior typing emit outcomes.",
            ("outcome",),
            registry=registry,
        )
        self._cross_module_overload = Counter(
            "cross_module_overload_total",
            "Cross-module overload events by workspace and severity.",
            ("workspace_id", "severity"),
            registry=registry,
        )
        self._attempts_stuck = Counter(
            "attempts_stuck_total",
            "Stuck send attempts reconciled by workspace and resolution.",
            ("workspace_id", "resolution"),
            registry=registry,
        )

    def gate_blocked(self, *, workspace_id: str, intent: str, reason: str) -> None:
        if not self.enabled:
            return
        self._gate_blocks.labels(workspace_id=workspace_id, intent=intent, reason=reason).inc()

    def gate_evaluate_duration(self, *, intent: str, cache_hit: bool) -> ContextManager[None]:
        if not self.enabled:
            return nullcontext()
        return self._timer(
            self._gate_evaluate_duration.labels(
                intent=intent,
                cache_hit=str(cache_hit).lower(),
            )
        )

    def quarantine_active(self, *, workspace_id: str, reason: str, value: int) -> None:
        if not self.enabled:
            return
        self._quarantine_active.labels(workspace_id=workspace_id, reason=reason).set(value)

    def account_total(self, *, workspace_id: str, value: int) -> None:
        if not self.enabled:
            return
        self._account_total.labels(workspace_id=workspace_id).set(value)

    def quarantine_opened(self, *, workspace_id: str, reason: str) -> None:
        if not self.enabled:
            return
        self._quarantine_opened.labels(workspace_id=workspace_id, reason=reason).inc()

    def quarantine_released(self, *, workspace_id: str, reason: str, mode: str) -> None:
        if not self.enabled:
            return
        self._quarantine_released.labels(
            workspace_id=workspace_id,
            reason=reason,
            mode=mode,
        ).inc()

    def ggr_score(self, *, workspace_id: str, bucket: str, score: float) -> None:
        if not self.enabled:
            return
        self._ggr_score.labels(workspace_id=workspace_id, bucket=bucket).observe(score)

    def flood_wait(self, *, workspace_id: str, account_id: str) -> None:
        if not self.enabled:
            return
        self._flood_wait.labels(
            workspace_id=workspace_id,
            account_id_hash=self.account_id_hash(account_id),
        ).inc()

    def attempt_send_duration(self, *, strategy: str) -> ContextManager[None]:
        if not self.enabled:
            return nullcontext()
        return self._timer(self._attempt_send_duration.labels(strategy=strategy))

    def reserve_outcome(self, *, outcome: ReserveOutcome | str) -> None:
        if not self.enabled:
            return
        self._reserve_outcomes.labels(outcome=outcome).inc()

    def typing_emit(self, *, outcome: TypingOutcome | str) -> None:
        if not self.enabled:
            return
        self._typing_emit.labels(outcome=outcome).inc()

    def cross_module_overload(self, *, workspace_id: str, severity: OverloadSeverity | str) -> None:
        if not self.enabled:
            return
        self._cross_module_overload.labels(workspace_id=workspace_id, severity=severity).inc()

    def attempts_stuck(
        self, *, workspace_id: str | None, resolution: AttemptResolution | str
    ) -> None:
        if not self.enabled:
            return
        self._attempts_stuck.labels(
            workspace_id=workspace_id or "unknown",
            resolution=resolution,
        ).inc()

    @staticmethod
    def account_id_hash(account_id: str) -> str:
        return hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:8]

    @contextmanager
    def _timer(self, histogram: Any) -> Iterator[None]:
        with histogram.time():
            yield


safety_metrics = SafetyMetrics()
