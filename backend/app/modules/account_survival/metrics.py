from __future__ import annotations

# pyright: reportMissingModuleSource=false

from typing import Any

from app.config import settings
from app.platform_bootstrap import patch_windows_platform_probe

try:
    import prometheus_client as _prometheus_client
except ImportError:  # pragma: no cover - keeps app importable before deps sync.
    _prometheus_client = None

patch_windows_platform_probe()


class AccountSurvivalMetrics:
    """Prometheus metrics for Advanced Warmup survival outcomes."""

    def __init__(
        self,
        *,
        registry: Any = None,
        enabled: bool | None = None,
    ) -> None:
        self.registry = (
            registry
            if registry is not None
            else (_prometheus_client.REGISTRY if _prometheus_client is not None else None)
        )
        self.enabled = (
            settings.metrics_enabled if enabled is None else enabled
        ) and _prometheus_client is not None
        if not self.enabled:
            return

        client = _prometheus_client
        assert client is not None

        self._survival_total = client.Counter(
            "account_survival_total",
            "Cumulative account survival lifecycle observations by state.",
            ("state", "workspace_id"),
            registry=self.registry,
        )
        self._survival_current = client.Gauge(
            "account_survival_current",
            "Current account survival lifecycle counts by state.",
            ("state", "workspace_id"),
            registry=self.registry,
        )
        self._survival_days = client.Gauge(
            "account_survival_days",
            "Account survival days by percentile label.",
            ("percentile", "workspace_id"),
            registry=self.registry,
        )
        self._warmup_completed = client.Counter(
            "warmup_session_completed_total",
            "Completed warmup sessions by preset.",
            ("preset", "workspace_id"),
            registry=self.registry,
        )
        self._warmup_action_executed = client.Counter(
            "warmup_action_executed_total",
            "Warmup action execution outcomes.",
            ("action_type", "result", "workspace_id"),
            registry=self.registry,
        )
        self._warmup_flood_wait = client.Counter(
            "warmup_flood_wait_total",
            "Warmup flood-wait incidents by action type.",
            ("action_type", "workspace_id"),
            registry=self.registry,
        )
        self._channel_health = client.Gauge(
            "warmup_channel_health_total",
            "Warmup channel health distribution by bucket.",
            ("bucket", "workspace_id"),
            registry=self.registry,
        )

    def account_survival_observed(self, *, state: str, workspace_id: str) -> None:
        if not self.enabled:
            return
        self._survival_total.labels(state=state, workspace_id=workspace_id).inc()

    def account_survival_current(self, *, state: str, workspace_id: str, value: int) -> None:
        if not self.enabled:
            return
        self._survival_current.labels(state=state, workspace_id=workspace_id).set(value)

    def account_survival_days(
        self, *, percentile: str, workspace_id: str, value: float | int | None
    ) -> None:
        if not self.enabled:
            return
        self._survival_days.labels(percentile=percentile, workspace_id=workspace_id).set(
            float(value or 0)
        )

    def warmup_session_completed(self, *, preset: str | None, workspace_id: str) -> None:
        if not self.enabled:
            return
        self._warmup_completed.labels(
            preset=_label(preset),
            workspace_id=workspace_id,
        ).inc()

    def warmup_action_executed(self, *, action_type: str, result: str, workspace_id: str) -> None:
        if not self.enabled:
            return
        self._warmup_action_executed.labels(
            action_type=_label(action_type),
            result=_label(result),
            workspace_id=workspace_id,
        ).inc()

    def warmup_flood_wait(self, *, action_type: str | None, workspace_id: str) -> None:
        if not self.enabled:
            return
        self._warmup_flood_wait.labels(
            action_type=_label(action_type),
            workspace_id=workspace_id,
        ).inc()

    def channel_health(self, *, bucket: str, workspace_id: str, value: int) -> None:
        if not self.enabled:
            return
        self._channel_health.labels(bucket=bucket, workspace_id=workspace_id).set(value)


def _label(value: str | None) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized else "unknown"


account_survival_metrics = AccountSurvivalMetrics()

__all__ = ["AccountSurvivalMetrics", "account_survival_metrics"]
