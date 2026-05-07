from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WarmupStrategy, new_id


PRESET_STRATEGIES = [
    {
        "name": "Мягкая подготовка",
        "description": "Самый осторожный 14-дневный план с минимальным темпом.",
        "tier_limits_json": {"cadence_hours": 24, "profile_required": True},
    },
    {
        "name": "Стандартная подготовка",
        "description": "Базовый 14-дневный план с ежедневным dry-run контролем.",
        "tier_limits_json": {"cadence_hours": 24, "profile_required": True},
    },
    {
        "name": "Строгая подготовка",
        "description": "План с повышенным вниманием к паузам, предупреждениям и ручной проверке.",
        "tier_limits_json": {"cadence_hours": 24, "manual_review": True},
    },
]


def seed_warmup_strategies(
    session: Session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> int:
    created = 0
    for preset in PRESET_STRATEGIES:
        exists = session.execute(
            select(WarmupStrategy.id).where(
                WarmupStrategy.workspace_id == workspace_id,
                WarmupStrategy.name == preset["name"],
            )
        ).first()
        if exists:
            continue
        session.add(
            WarmupStrategy(
                id=new_id(),
                workspace_id=workspace_id,
                name=preset["name"],
                description=preset["description"],
                tier_limits_json=preset["tier_limits_json"],
                target_channels_json=[],
                is_preset=True,
            )
        )
        created += 1
    session.commit()
    return created


def main() -> None:
    with SessionLocal() as session:
        created = seed_warmup_strategies(session)
    print(f"created={created}")


if __name__ == "__main__":
    main()
