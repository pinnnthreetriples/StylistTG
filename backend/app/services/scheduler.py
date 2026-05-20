from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, settings
from app.db import SessionLocal
from app.services.account_status_monitor import run_account_status_monitor_tick

ACCOUNT_STATUS_MONITOR_TICK_SECONDS = 600


@dataclass(frozen=True)
class SchedulerReport:
    enabled: bool
    mode: str
    planned_queues: list[str]
    planned_ticks: dict[str, int]
    destructive_actions_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "planned_queues": self.planned_queues,
            "planned_ticks": self.planned_ticks,
            "destructive_actions_enabled": self.destructive_actions_enabled,
        }


def scheduler_report(config: Settings = settings) -> SchedulerReport:
    return SchedulerReport(
        enabled=config.scheduler_enabled,
        mode="report_only" if not config.scheduler_enabled else "safe_enqueue",
        planned_queues=["scheduler_jobs", "maintenance_jobs"],
        planned_ticks={"account_status_monitor": ACCOUNT_STATUS_MONITOR_TICK_SECONDS},
    )


def account_status_monitor_tick() -> int:
    with SessionLocal() as session:
        observations = run_account_status_monitor_tick(session)
        session.commit()
        return len(observations)
