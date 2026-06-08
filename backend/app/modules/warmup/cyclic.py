from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WarmupSession, WarmupStrategy, utc_now
from app.modules.warmup.commands import create_warmup_session
from app.modules.warmup.errors import WarmupStrategyNotFoundError
from app.modules.warmup.events import write_warmup_event


MAX_CYCLE_DAYS = 30


@dataclass(frozen=True)
class CycleWindowStatus:
    in_window: bool
    completed: bool
    active_window_start: datetime | None
    active_window_end: datetime | None
    next_window_start: datetime | None
    current_cycle: int
    active_hours_total: int


def setup_cyclic_warmup(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    start_hour: int,
    end_hour: int,
    days_total: int,
    strategy_preset: str = "standard",
    now: datetime | None = None,
) -> WarmupSession:
    timestamp = now or utc_now()
    strategy = _strategy_for_preset(session, workspace_id=workspace_id, preset=strategy_preset)
    warmup_session = create_warmup_session(
        session,
        account_id=account_id,
        strategy_id=strategy.id,
        workspace_id=workspace_id,
        now=timestamp,
    )
    warmup_session.duration_days = _clamp_days(days_total)
    warmup_session.cycle_config_json = {
        "start_hour": _valid_hour(start_hour),
        "end_hour": _valid_hour(end_hour),
        "days_total": warmup_session.duration_days,
        "current_cycle": 1,
        "started_at": timestamp.astimezone(UTC).isoformat(),
        "active_hours_total": compute_total_active_hours(
            {"start_hour": start_hour, "end_hour": end_hour, "days_total": days_total}
        ),
    }
    write_warmup_event(
        session,
        warmup_session,
        "cyclic.started",
        {
            "start_hour": _valid_hour(start_hour),
            "end_hour": _valid_hour(end_hour),
            "days_total": warmup_session.duration_days,
        },
    )
    session.flush()
    return warmup_session


def setup_cyclic_warmups(
    session: Session,
    *,
    account_ids: list[str],
    workspace_id: str,
    start_hour: int,
    end_hour: int,
    days_total: int,
    strategy_preset: str = "standard",
    now: datetime | None = None,
) -> list[WarmupSession]:
    return [
        setup_cyclic_warmup(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
            start_hour=start_hour,
            end_hour=end_hour,
            days_total=days_total,
            strategy_preset=strategy_preset,
            now=now,
        )
        for account_id in account_ids
    ]


def cycle_window_status(
    cycle_config: dict[str, Any] | None,
    now: datetime,
    timezone: str | None,
) -> CycleWindowStatus | None:
    if not cycle_config:
        return None
    window = compute_cycle_active_window(cycle_config, now, timezone)
    active_hours_total = compute_total_active_hours(cycle_config)
    if window is not None:
        start, end = window
        return CycleWindowStatus(
            in_window=start <= now.astimezone(UTC) < end,
            completed=False,
            active_window_start=start,
            active_window_end=end,
            next_window_start=None,
            current_cycle=_cycle_number(cycle_config, start, timezone),
            active_hours_total=active_hours_total,
        )
    next_start = _next_window_start(cycle_config, now, timezone)
    return CycleWindowStatus(
        in_window=False,
        completed=next_start is None,
        active_window_start=None,
        active_window_end=None,
        next_window_start=next_start,
        current_cycle=_current_cycle(cycle_config, now, timezone),
        active_hours_total=active_hours_total,
    )


def schedule_next_cycle(warmup_session: WarmupSession, *, now: datetime) -> None:
    status = cycle_window_status(warmup_session.cycle_config_json, now, warmup_session.timezone)
    if status is None:
        return
    config = dict(warmup_session.cycle_config_json or {})
    config["current_cycle"] = min(status.current_cycle, int(config.get("days_total") or 1))
    warmup_session.cycle_config_json = config
    if status.next_window_start is not None:
        warmup_session.next_micro_session_at = status.next_window_start
        warmup_session.next_step_at = status.next_window_start
    warmup_session.updated_at = now


def compute_cycle_active_window(
    cycle_config: dict[str, Any],
    now: datetime,
    timezone: str | None = None,
) -> tuple[datetime, datetime] | None:
    zone = _zone(timezone)
    local_now = _aware(now).astimezone(zone)
    start_hour = _valid_hour(cycle_config.get("start_hour", 0))
    end_hour = _valid_hour(cycle_config.get("end_hour", 0))
    if start_hour == end_hour:
        return None

    if start_hour < end_hour:
        start = _local_datetime(local_now.date(), start_hour, zone)
        end = _local_datetime(local_now.date(), end_hour, zone)
    elif local_now.hour >= start_hour:
        start = _local_datetime(local_now.date(), start_hour, zone)
        end = _local_datetime(local_now.date() + timedelta(days=1), end_hour, zone)
    else:
        start = _local_datetime(local_now.date() - timedelta(days=1), start_hour, zone)
        end = _local_datetime(local_now.date(), end_hour, zone)

    start_utc = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    if not (start_utc <= _aware(now).astimezone(UTC) < end_utc):
        return None
    cycle_number = _cycle_number(cycle_config, start_utc, timezone)
    days_total = _clamp_days(cycle_config.get("days_total", 1))
    if cycle_number < 1 or cycle_number > days_total:
        return None
    return start_utc, end_utc


def is_in_active_window(
    cycle_config: dict[str, Any],
    now: datetime,
    timezone: str | None = None,
) -> bool:
    return compute_cycle_active_window(cycle_config, now, timezone) is not None


def compute_total_active_hours(cycle_config: dict[str, Any]) -> int:
    start_hour = _valid_hour(cycle_config.get("start_hour", 0))
    end_hour = _valid_hour(cycle_config.get("end_hour", 0))
    days_total = _clamp_days(cycle_config.get("days_total", 1))
    if start_hour == end_hour:
        return 0
    hours_per_day = end_hour - start_hour if start_hour < end_hour else (24 - start_hour) + end_hour
    return hours_per_day * days_total


def _strategy_for_preset(session: Session, *, workspace_id: str, preset: str) -> WarmupStrategy:
    strategy = session.execute(
        select(  # nosemgrep: missing-workspace-id-filter - workspace-scoped lookup intentionally falls back to global presets.
            WarmupStrategy
        )
        .where(
            (
                (WarmupStrategy.workspace_id == workspace_id)
                | (WarmupStrategy.workspace_id.is_(None))
            ),
            WarmupStrategy.preset_kind == preset,
        )
        .order_by(WarmupStrategy.workspace_id.desc().nullslast(), WarmupStrategy.is_preset.desc())
        .limit(1)
    ).scalar_one_or_none()
    if strategy is None:
        raise WarmupStrategyNotFoundError()
    return strategy


def _next_window_start(
    cycle_config: dict[str, Any],
    now: datetime,
    timezone: str | None,
) -> datetime | None:
    zone = _zone(timezone)
    local_now = _aware(now).astimezone(zone)
    start_hour = _valid_hour(cycle_config.get("start_hour", 0))
    for offset in range(0, _clamp_days(cycle_config.get("days_total", 1)) + 1):
        candidate_date = local_now.date() + timedelta(days=offset)
        candidate = _local_datetime(candidate_date, start_hour, zone).astimezone(UTC)
        if candidate <= _aware(now).astimezone(UTC):
            continue
        cycle_number = _cycle_number(cycle_config, candidate, timezone)
        if 1 <= cycle_number <= _clamp_days(cycle_config.get("days_total", 1)):
            return candidate
    return None


def _cycle_number(
    cycle_config: dict[str, Any], window_start: datetime, timezone: str | None
) -> int:
    zone = _zone(timezone)
    started_at = _parse_started_at(cycle_config).astimezone(zone)
    window_local = _aware(window_start).astimezone(zone)
    return (window_local.date() - started_at.date()).days + 1


def _current_cycle(cycle_config: dict[str, Any], now: datetime, timezone: str | None) -> int:
    zone = _zone(timezone)
    started_at = _parse_started_at(cycle_config).astimezone(zone)
    local_now = _aware(now).astimezone(zone)
    return max(1, (local_now.date() - started_at.date()).days + 1)


def _parse_started_at(cycle_config: dict[str, Any]) -> datetime:
    raw = cycle_config.get("started_at")
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return utc_now()


def _local_datetime(date_value: Any, hour: int, zone: ZoneInfo) -> datetime:
    return datetime.combine(date_value, time(hour=hour), tzinfo=zone)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _zone(timezone: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(timezone or "UTC")
    except ZoneInfoNotFoundError, AttributeError:
        return ZoneInfo("UTC")


def _valid_hour(value: Any) -> int:
    return max(0, min(23, int(value)))


def _clamp_days(value: Any) -> int:
    return max(1, min(MAX_CYCLE_DAYS, int(value)))


__all__ = [
    "CycleWindowStatus",
    "compute_cycle_active_window",
    "compute_total_active_hours",
    "cycle_window_status",
    "is_in_active_window",
    "schedule_next_cycle",
    "setup_cyclic_warmup",
    "setup_cyclic_warmups",
]
