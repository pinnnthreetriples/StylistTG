from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings, settings


@dataclass(frozen=True)
class SchedulerReport:
    enabled: bool
    mode: str
    planned_queues: list[str]
    destructive_actions_enabled: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "planned_queues": self.planned_queues,
            "destructive_actions_enabled": self.destructive_actions_enabled,
        }


def scheduler_report(config: Settings = settings) -> SchedulerReport:
    return SchedulerReport(
        enabled=config.scheduler_enabled,
        mode="report_only" if not config.scheduler_enabled else "safe_enqueue",
        planned_queues=["scheduler_jobs", "maintenance_jobs"],
    )
