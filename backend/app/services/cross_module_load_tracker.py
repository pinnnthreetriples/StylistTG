from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.contracts.cross_module_load import CrossModuleLoad, CrossModuleName
from app.models import Account, CrossModuleLoadBucket, new_id, utc_now

SafetyMode = Literal["conservative", "balanced", "aggressive"]
ThresholdVerdict = Literal["ok", "warning", "blocked"]


@dataclass(frozen=True)
class LoadThreshold:
    hour: int
    day: int


LOAD_THRESHOLDS: dict[SafetyMode, LoadThreshold] = {
    "conservative": LoadThreshold(hour=12, day=80),
    "balanced": LoadThreshold(hour=25, day=200),
    "aggressive": LoadThreshold(hour=60, day=500),
}

_MODULE_COLUMNS: dict[CrossModuleName, str] = {
    "warmup": "warmup_actions",
    "commenting": "commenting_actions",
    "editing": "editing_actions",
    "other": "other_actions",
}


class CrossModuleLoadAccountNotFound(LookupError):
    pass


def _current_bucket_start(now: datetime | None = None) -> datetime:
    return (now or utc_now()).replace(minute=0, second=0, microsecond=0)


def _insert_for_session(session: Session):
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        return pg_insert(CrossModuleLoadBucket)
    if dialect_name == "sqlite":
        return sqlite_insert(CrossModuleLoadBucket)
    return None


def _require_account_in_workspace(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
) -> None:
    account_exists = session.scalar(
        select(Account.id)
        .where(Account.workspace_id == workspace_id)
        .where(Account.id == account_id)
    )
    if account_exists is None:
        raise CrossModuleLoadAccountNotFound(account_id)


def track(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    module: CrossModuleName,
    count: int = 1,
) -> None:
    if count <= 0:
        raise ValueError("count must be positive")
    column_name = _MODULE_COLUMNS[module]
    bucket_start = _current_bucket_start()
    _require_account_in_workspace(session, workspace_id=workspace_id, account_id=account_id)

    insert_stmt = _insert_for_session(session)
    if insert_stmt is None:
        _track_without_native_upsert(
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            bucket_start=bucket_start,
            column_name=column_name,
            count=count,
        )
        return

    values = {
        "id": new_id(),
        "workspace_id": workspace_id,
        "account_id": account_id,
        "bucket_start": bucket_start,
        "warmup_actions": 0,
        "commenting_actions": 0,
        "editing_actions": 0,
        "other_actions": 0,
        column_name: count,
    }
    insert_stmt = insert_stmt.values(**values)
    update_column = getattr(CrossModuleLoadBucket, column_name)
    statement = insert_stmt.on_conflict_do_update(
        index_elements=["workspace_id", "account_id", "bucket_start"],
        set_={column_name: update_column + count},
    )
    session.execute(statement)
    session.flush()


def _track_without_native_upsert(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    bucket_start: datetime,
    column_name: str,
    count: int,
) -> None:
    bucket = session.execute(
        select(CrossModuleLoadBucket)
        .where(CrossModuleLoadBucket.workspace_id == workspace_id)
        .where(CrossModuleLoadBucket.account_id == account_id)
        .where(CrossModuleLoadBucket.bucket_start == bucket_start)
    ).scalar_one_or_none()
    if bucket is None:
        bucket = CrossModuleLoadBucket(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            bucket_start=bucket_start,
        )
        session.add(bucket)
    setattr(bucket, column_name, getattr(bucket, column_name) + count)
    session.flush()


def current_load(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
) -> CrossModuleLoad:
    current_bucket = _current_bucket_start()
    window_start = current_bucket - timedelta(hours=23)

    row = session.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (
                            CrossModuleLoadBucket.bucket_start == current_bucket,
                            CrossModuleLoadBucket.total_actions,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(CrossModuleLoadBucket.total_actions), 0),
            func.coalesce(func.sum(CrossModuleLoadBucket.warmup_actions), 0),
            func.coalesce(func.sum(CrossModuleLoadBucket.commenting_actions), 0),
            func.coalesce(func.sum(CrossModuleLoadBucket.editing_actions), 0),
            func.coalesce(func.sum(CrossModuleLoadBucket.other_actions), 0),
        )
        .where(CrossModuleLoadBucket.workspace_id == workspace_id)
        .where(CrossModuleLoadBucket.account_id == account_id)
        .where(CrossModuleLoadBucket.bucket_start >= window_start)
    ).one()

    return CrossModuleLoad(
        last_hour=int(row[0] or 0),
        last_24h=int(row[1] or 0),
        breakdown={
            "warmup": int(row[2] or 0),
            "commenting": int(row[3] or 0),
            "editing": int(row[4] or 0),
            "other": int(row[5] or 0),
        },
    )


def evaluate_threshold(load: CrossModuleLoad, mode: SafetyMode) -> ThresholdVerdict:
    thresholds = LOAD_THRESHOLDS[mode]
    if load.last_hour >= thresholds.hour or load.last_24h >= thresholds.day:
        return "blocked"
    if load.last_hour >= thresholds.hour * 0.8 or load.last_24h >= thresholds.day * 0.8:
        return "warning"
    return "ok"


__all__ = [
    "CrossModuleLoadAccountNotFound",
    "LOAD_THRESHOLDS",
    "current_load",
    "evaluate_threshold",
    "track",
]
