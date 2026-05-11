from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupExecutionMode,
    WarmupPresetKind,
    WarmupStrategy,
    new_id,
)


def _baseline_limits(
    *,
    duration_days: int,
    start_feed: int,
    end_feed: int,
    max_joins: int,
    max_p2p: int,
) -> dict[str, dict[str, int]]:
    """Generate per-day ceiling matrix.

    Day 1 is seeded with `start_feed` reads, 0 joins, 0 p2p.
    Day N (duration_days) reaches `end_feed` reads, `max_joins` joins, `max_p2p` p2p.
    Intermediate days interpolate linearly. Joins start on day ceil(N/3); p2p starts on day ceil(2*N/3).
    """
    import math

    matrix: dict[str, dict[str, int]] = {}
    joins_start = max(1, math.ceil(duration_days / 3))
    p2p_start = max(1, math.ceil(2 * duration_days / 3))
    for day in range(1, duration_days + 1):
        fraction = (day - 1) / max(1, duration_days - 1)
        feed_read = round(start_feed + (end_feed - start_feed) * fraction)
        if day < joins_start:
            join_chat = 0
        else:
            join_fraction = (day - joins_start) / max(1, duration_days - joins_start)
            join_chat = round(max_joins * join_fraction)
        if day < p2p_start:
            p2p_send = 0
        else:
            p2p_fraction = (day - p2p_start) / max(1, duration_days - p2p_start)
            p2p_send = round(max_p2p * p2p_fraction)
        matrix[str(day)] = {
            "feed_read": feed_read,
            "join_chat": join_chat,
            "p2p_send": p2p_send,
        }
    return matrix


def _preset_payload(
    *,
    preset_kind: str,
    duration_days: int,
    description: str,
    ui_summary: dict[str, Any],
    limits_overrides: dict[str, int],
    session_window: dict[str, Any],
) -> dict[str, Any]:
    return {
        "preset_kind": preset_kind,
        "duration_days": duration_days,
        "execution_mode": WarmupExecutionMode.DRY_RUN.value,
        "description": description,
        "daily_action_limits_json": _baseline_limits(
            duration_days=duration_days,
            start_feed=limits_overrides["start_feed"],
            end_feed=limits_overrides["end_feed"],
            max_joins=limits_overrides["max_joins"],
            max_p2p=limits_overrides["max_p2p"],
        ),
        "session_window_config_json": session_window,
        "ui_summary_json": ui_summary,
        "tier_limits_json": {
            "cadence_hours": 24,
            "profile_required": True,
        },
    }


PRESET_STRATEGIES: list[dict[str, Any]] = [
    {
        "name": "Мягкая подготовка",
        **_preset_payload(
            preset_kind=WarmupPresetKind.EXPRESS.value,
            duration_days=7,
            description="Экспресс-план на 7 дней: мягкий темп, подходит для уже прогретой истории или быстрой повторной итерации.",
            ui_summary={
                "audience_hint": "Для аккаунтов с уже прогретой историей или быстрых итераций.",
                "speed_hint": "Быстрый темп: завершение за 7 дней.",
                "risk_level": "low",
            },
            limits_overrides={
                "start_feed": 3,
                "end_feed": 40,
                "max_joins": 2,
                "max_p2p": 5,
            },
            session_window={
                "micro_sessions_per_day": {"min": 3, "max": 5},
                "minutes_per_session": {"min": 2, "max": 6},
                "quiet_hours_local": {"start": 23, "end": 8},
            },
        ),
    },
    {
        "name": "Стандартная подготовка",
        **_preset_payload(
            preset_kind=WarmupPresetKind.STANDARD.value,
            duration_days=14,
            description="Стандартный 14-дневный план с ежедневной подготовкой без лишней агрессии.",
            ui_summary={
                "audience_hint": "Типовой выбор для большинства новых аккаунтов.",
                "speed_hint": "Сбалансированный темп: 14 дней.",
                "risk_level": "medium",
            },
            limits_overrides={
                "start_feed": 5,
                "end_feed": 80,
                "max_joins": 2,
                "max_p2p": 5,
            },
            session_window={
                "micro_sessions_per_day": {"min": 3, "max": 6},
                "minutes_per_session": {"min": 2, "max": 7},
                "quiet_hours_local": {"start": 23, "end": 8},
            },
        ),
    },
    {
        "name": "Строгая подготовка",
        **_preset_payload(
            preset_kind=WarmupPresetKind.HARDENED.value,
            duration_days=21,
            description="Усиленный 21-дневный план с медленным стартом и повышенной осторожностью для новых виртуальных номеров.",
            ui_summary={
                "audience_hint": "Для новых виртуальных номеров и подозрительных гео-фингерпринтов.",
                "speed_hint": "Медленный темп: 21 день для максимальной безопасности.",
                "risk_level": "high",
            },
            limits_overrides={
                "start_feed": 2,
                "end_feed": 120,
                "max_joins": 3,
                "max_p2p": 8,
            },
            session_window={
                "micro_sessions_per_day": {"min": 2, "max": 5},
                "minutes_per_session": {"min": 2, "max": 7},
                "quiet_hours_local": {"start": 22, "end": 9},
            },
        ),
    },
]


def seed_warmup_strategies(
    session: Session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> int:
    """Create or upgrade preset warmup strategies idempotently.

    Returns the number of newly created rows. Existing rows whose new fields
    diverge from the canonical preset payload are updated in place (idempotent
    upgrade path for Фаза 0a).
    """
    created = 0
    for preset in PRESET_STRATEGIES:
        existing = (
            session.execute(
                select(WarmupStrategy).where(
                    WarmupStrategy.workspace_id == workspace_id,
                    WarmupStrategy.name == preset["name"],
                )
            )
            .scalars()
            .first()
        )
        if existing is None:
            session.add(
                WarmupStrategy(
                    id=new_id(),
                    workspace_id=workspace_id,
                    name=preset["name"],
                    description=preset["description"],
                    tier_limits_json=preset["tier_limits_json"],
                    target_channels_json=[],
                    is_preset=True,
                    execution_mode=preset["execution_mode"],
                    preset_kind=preset["preset_kind"],
                    duration_days=preset["duration_days"],
                    daily_action_limits_json=preset["daily_action_limits_json"],
                    session_window_config_json=preset["session_window_config_json"],
                    ui_summary_json=preset["ui_summary_json"],
                )
            )
            created += 1
            continue
        # Idempotent upgrade of legacy preset rows that predate the new fields.
        existing.description = preset["description"]
        existing.tier_limits_json = preset["tier_limits_json"]
        existing.execution_mode = preset["execution_mode"]
        existing.preset_kind = preset["preset_kind"]
        existing.duration_days = preset["duration_days"]
        existing.daily_action_limits_json = preset["daily_action_limits_json"]
        existing.session_window_config_json = preset["session_window_config_json"]
        existing.ui_summary_json = preset["ui_summary_json"]
    session.commit()
    return created


def main() -> None:
    with SessionLocal() as session:
        created = seed_warmup_strategies(session)
    print(f"created={created}")


if __name__ == "__main__":
    main()
