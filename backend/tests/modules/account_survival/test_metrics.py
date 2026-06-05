from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.contracts.queues import MAINTENANCE_QUEUE_NAME
from app.models import AccountSurvivalMetric, WarmupChannelState, new_id
from app.modules.account_survival import events
from app.modules.account_survival import metrics_updater
from app.modules.account_survival import metrics as metrics_module
from app.modules.account_survival.metrics import AccountSurvivalMetrics
from app.modules.account_survival.metrics_updater import (
    SURVIVAL_METRICS_WORKFLOW_TYPE,
    update_survival_metrics,
)
from app.modules.contracts import WorkflowArgsMode
from app.modules.registry import get_workflow_spec
from app.services.scheduler import (
    SURVIVAL_METRICS_JOB_ID_PREFIX,
    SURVIVAL_METRICS_TICK_SECONDS,
    enqueue_survival_metrics_tick,
    scheduler_report,
)
from tests.helpers.factories import seed_account

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_survival_event_hooks_increment_prometheus_counters(db_session, monkeypatch) -> None:
    registry, metrics = _fake_metrics(monkeypatch)
    monkeypatch.setattr(events, "account_survival_metrics", metrics)
    account = seed_account(db_session)

    events.on_account_terminal(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        terminal_status="banned",
        now=NOW + timedelta(days=3),
    )

    assert (
        registry.get_sample_value(
            "account_survival_total",
            {"state": "alive", "workspace_id": account.workspace_id},
        )
        == 1.0
    )
    assert (
        registry.get_sample_value(
            "account_survival_total",
            {"state": "banned", "workspace_id": account.workspace_id},
        )
        == 1.0
    )


def test_warmup_event_hooks_increment_completion_action_and_flood_wait(
    db_session, monkeypatch
) -> None:
    registry, metrics = _fake_metrics(monkeypatch)
    monkeypatch.setattr(events, "account_survival_metrics", metrics)
    account = seed_account(db_session)

    events.on_warmup_completed(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW,
        preset="standard",
    )
    events.on_warmup_action_executed(
        action_type="react_to_post",
        result="success",
        workspace_id=account.workspace_id,
    )
    events.on_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW,
        action_type="react_to_post",
    )

    assert (
        registry.get_sample_value(
            "warmup_session_completed_total",
            {"preset": "standard", "workspace_id": account.workspace_id},
        )
        == 1.0
    )
    assert (
        registry.get_sample_value(
            "warmup_action_executed_total",
            {
                "action_type": "react_to_post",
                "result": "success",
                "workspace_id": account.workspace_id,
            },
        )
        == 1.0
    )
    assert (
        registry.get_sample_value(
            "warmup_flood_wait_total",
            {"action_type": "react_to_post", "workspace_id": account.workspace_id},
        )
        == 1.0
    )


def test_survival_metrics_updater_sets_gauges(db_session, monkeypatch) -> None:
    registry, metrics = _fake_metrics(monkeypatch)
    account = seed_account(db_session)
    metric = db_session.query(AccountSurvivalMetric).filter_by(account_id=account.id).one()
    metric.imported_at = NOW - timedelta(days=10)
    metric.banned_at = NOW
    metric.updated_at = NOW
    db_session.add_all(
        [
            WarmupChannelState(
                id=new_id(),
                workspace_id=account.workspace_id,
                account_id=account.id,
                channel_ref="@healthy",
                health_score=0.9,
                created_at=NOW,
                updated_at=NOW,
            ),
            WarmupChannelState(
                id=new_id(),
                workspace_id=account.workspace_id,
                account_id=account.id,
                channel_ref="@warning",
                health_score=0.4,
                created_at=NOW,
                updated_at=NOW,
            ),
            WarmupChannelState(
                id=new_id(),
                workspace_id=account.workspace_id,
                account_id=account.id,
                channel_ref="@blacklisted",
                health_score=0.1,
                created_at=NOW,
                updated_at=NOW,
            ),
        ]
    )
    db_session.flush()

    assert update_survival_metrics(db_session, metrics=metrics) == 1

    assert (
        registry.get_sample_value(
            "account_survival_current",
            {"state": "banned", "workspace_id": account.workspace_id},
        )
        == 1.0
    )
    assert (
        registry.get_sample_value(
            "account_survival_days",
            {"percentile": "p50", "workspace_id": account.workspace_id},
        )
        == 10.0
    )
    assert (
        registry.get_sample_value(
            "warmup_channel_health_total",
            {"bucket": "healthy", "workspace_id": account.workspace_id},
        )
        == 1.0
    )
    assert (
        registry.get_sample_value(
            "warmup_channel_health_total",
            {"bucket": "warning", "workspace_id": account.workspace_id},
        )
        == 1.0
    )
    assert (
        registry.get_sample_value(
            "warmup_channel_health_total",
            {"bucket": "blacklisted", "workspace_id": account.workspace_id},
        )
        == 1.0
    )


def test_survival_metrics_workflow_is_registered() -> None:
    spec = get_workflow_spec(SURVIVAL_METRICS_WORKFLOW_TYPE)

    assert spec.queue_name == MAINTENANCE_QUEUE_NAME
    assert spec.args_mode == WorkflowArgsMode.NONE
    assert (
        spec.handler_path
        == "app.modules.account_survival.metrics_updater:update_survival_metrics_workflow"
    )


def test_scheduler_report_registers_hourly_survival_metrics_tick() -> None:
    report = scheduler_report()

    assert report.planned_ticks["account_survival_metrics"] == SURVIVAL_METRICS_TICK_SECONDS


def test_enqueue_survival_metrics_tick_uses_maintenance_queue_and_hour_bucket(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    seen_queues: list[str] = []

    def fake_get_queue(name: str):
        seen_queues.append(name)
        return type(
            "FakeQueue", (), {"enqueue_call": lambda _self, **kwargs: calls.append(kwargs)}
        )()

    monkeypatch.setattr("app.job_queue.rq.get_queue", fake_get_queue)

    assert enqueue_survival_metrics_tick(now=(SURVIVAL_METRICS_TICK_SECONDS * 9) + 10)

    assert seen_queues == ["maintenance_jobs"]
    assert calls == [
        {
            "func": metrics_updater.update_survival_metrics_workflow,
            "job_id": f"{SURVIVAL_METRICS_JOB_ID_PREFIX}-9",
            "unique": True,
        }
    ]


def _fake_metrics(monkeypatch) -> tuple["_FakeRegistry", AccountSurvivalMetrics]:
    registry = _FakeRegistry()
    monkeypatch.setattr(metrics_module, "_prometheus_client", _FakePrometheusClient)
    return registry, AccountSurvivalMetrics(registry=registry, enabled=True)


class _FakeRegistry:
    def __init__(self) -> None:
        self.samples: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}

    def get_sample_value(self, name: str, labels: dict[str, str]) -> float | None:
        return self.samples.get((name, tuple(sorted(labels.items()))))


class _FakeMetric:
    def __init__(
        self,
        name: str,
        _documentation: str,
        _labelnames: tuple[str, ...],
        *,
        registry: _FakeRegistry,
    ) -> None:
        self.name = name
        self.registry = registry
        self.label_values: dict[str, str] = {}

    def labels(self, **labels: str) -> "_FakeMetric":
        child = _FakeMetric(self.name, "", (), registry=self.registry)
        child.label_values = {key: str(value) for key, value in labels.items()}
        return child

    def inc(self, amount: float = 1.0) -> None:
        key = self._key()
        self.registry.samples[key] = self.registry.samples.get(key, 0.0) + amount

    def set(self, value: float) -> None:
        self.registry.samples[self._key()] = float(value)

    def _key(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        return self.name, tuple(sorted(self.label_values.items()))


class _FakePrometheusClient:
    REGISTRY = _FakeRegistry()

    @staticmethod
    def Counter(
        name: str,
        documentation: str,
        labelnames: tuple[str, ...],
        *,
        registry: _FakeRegistry,
    ) -> _FakeMetric:
        return _FakeMetric(name, documentation, labelnames, registry=registry)

    @staticmethod
    def Gauge(
        name: str,
        documentation: str,
        labelnames: tuple[str, ...],
        *,
        registry: _FakeRegistry,
    ) -> _FakeMetric:
        return _FakeMetric(name, documentation, labelnames, registry=registry)
