from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import timedelta
import hashlib
import json
import socket
import sys
import traceback
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    Account,
    AccountBehaviorProfile,
    AccountGgrScore,
    NeuroCommentEvent,
    new_id,
    utc_now,
)

GRACE_PERIOD_DAYS = 30
BALANCED_TYPING_CPM = 200
BALANCED_TYPO_RATE = 0.02
BALANCED_PROFILE_VIEW_PROBABILITY = 0.15
BALANCED_SCROLL_PROBABILITY = 0.30
BALANCED_MESSAGE_DELETION_PROBABILITY = 0.005


@dataclass
class BackfillStats:
    workspace_id: str
    dry_run: bool
    batch_size: int
    batch_run_id: str = field(default_factory=new_id)
    accounts_seen: int = 0
    batches_committed: int = 0
    ggr_created: int = 0
    behavior_created: int = 0
    origins_set: int = 0
    grace_periods_set: int = 0
    events_created: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_backfill(
    session: Session,
    *,
    workspace_id: str,
    batch_size: int,
    dry_run: bool,
    skip_existing: bool,
    executed_by: str | None = None,
) -> BackfillStats:
    if batch_size <= 0:
        raise ValueError("batch-size must be greater than zero")
    _validate_workspace_id(workspace_id)
    stats = BackfillStats(workspace_id=workspace_id, dry_run=dry_run, batch_size=batch_size)
    account_ids = list(
        session.execute(
            select(Account.id).where(Account.workspace_id == workspace_id).order_by(Account.id)
        ).scalars()
    )
    if not account_ids:
        return stats

    actor = executed_by or f"backfill_safety_pipeline:{socket.gethostname()}"
    for offset in range(0, len(account_ids), batch_size):
        batch_ids = account_ids[offset : offset + batch_size]
        if not dry_run:
            _lock_workspace(session, workspace_id)
        for account in session.execute(
            select(Account)
            .where(Account.workspace_id == workspace_id)
            .where(Account.id.in_(batch_ids))
            .order_by(Account.id)
        ).scalars():
            actions = _planned_actions(session, account)
            if skip_existing and not actions:
                continue
            stats.accounts_seen += 1
            if dry_run or not actions:
                _count_actions(stats, actions)
                continue
            applied = _apply_actions(session, account, actions, stats=stats, executed_by=actor)
            _count_actions(stats, applied)
        if dry_run:
            continue
        session.commit()
        stats.batches_committed += 1
    return stats


def _planned_actions(session: Session, account: Account) -> set[str]:
    actions: set[str] = set()
    ggr_exists = session.scalar(
        select(AccountGgrScore.id)
        .where(AccountGgrScore.workspace_id == account.workspace_id)
        .where(AccountGgrScore.account_id == account.id)
    )
    if ggr_exists is None:
        actions.add("ggr_created")
    behavior_exists = session.scalar(
        select(AccountBehaviorProfile.id)
        .where(AccountBehaviorProfile.workspace_id == account.workspace_id)
        .where(AccountBehaviorProfile.account_id == account.id)
    )
    if behavior_exists is None:
        actions.add("behavior_created")
    if account.origin is None:
        actions.add("origin_set")
    if account.safety_grace_period_until is None:
        actions.add("grace_period_set")
    return actions


def _apply_actions(
    session: Session,
    account: Account,
    actions: set[str],
    *,
    stats: BackfillStats,
    executed_by: str,
) -> set[str]:
    now = utc_now()
    applied: set[str] = set()
    if "ggr_created" in actions and _insert_ggr_score(session, account, now=now):
        applied.add("ggr_created")
    if "behavior_created" in actions and _insert_behavior_profile(session, account, now=now):
        applied.add("behavior_created")
    if "origin_set" in actions:
        account.origin = "imported"
        applied.add("origin_set")
    if "grace_period_set" in actions:
        account.safety_grace_period_until = now + timedelta(days=GRACE_PERIOD_DAYS)
        applied.add("grace_period_set")
    if not applied:
        return applied
    session.add(
        NeuroCommentEvent(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            event_type="safety_backfill_executed",
            event_level="info",
            message="Safety pipeline backfill executed for account.",
            data_json={
                "batch_run_id": stats.batch_run_id,
                "actions_taken": sorted(applied),
                "dry_run": stats.dry_run,
                "executed_by": executed_by,
            },
            created_at=now,
        )
    )
    stats.events_created += 1
    return applied


def _count_actions(stats: BackfillStats, actions: set[str]) -> None:
    if "ggr_created" in actions:
        stats.ggr_created += 1
    if "behavior_created" in actions:
        stats.behavior_created += 1
    if "origin_set" in actions:
        stats.origins_set += 1
    if "grace_period_set" in actions:
        stats.grace_periods_set += 1


def _stable_seed(account_id: str) -> int:
    return int(hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:8], 16) % (2**31)


def _lock_workspace(session: Session, workspace_id: str) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"backfill:{workspace_id}"},
    )


def _insert_ggr_score(session: Session, account: Account, *, now) -> bool:
    values = {
        "id": new_id(),
        "workspace_id": account.workspace_id,
        "account_id": account.id,
        "score": 5.0,
        "bucket": "medium",
        "breakdown_json": {},
        "previous_score": None,
        "last_calculated_at": None,
        "next_calculation_at": now,
        "created_at": now,
        "updated_at": now,
    }
    result = session.execute(
        _insert_do_nothing(session, AccountGgrScore, values, ["workspace_id", "account_id"])
    )
    return int(result.rowcount or 0) > 0


def _insert_behavior_profile(session: Session, account: Account, *, now) -> bool:
    values = {
        "id": new_id(),
        "workspace_id": account.workspace_id,
        "account_id": account.id,
        "typing_speed_baseline_cpm": BALANCED_TYPING_CPM,
        "typo_rate_baseline": BALANCED_TYPO_RATE,
        "profile_view_probability_baseline": BALANCED_PROFILE_VIEW_PROBABILITY,
        "scroll_probability_baseline": BALANCED_SCROLL_PROBABILITY,
        "message_deletion_probability_baseline": BALANCED_MESSAGE_DELETION_PROBABILITY,
        "action_sequence_seed": _stable_seed(account.id),
        "created_at": now,
        "updated_at": now,
    }
    result = session.execute(
        _insert_do_nothing(session, AccountBehaviorProfile, values, ["workspace_id", "account_id"])
    )
    return int(result.rowcount or 0) > 0


def _insert_do_nothing(
    session: Session, model, values: dict[str, object], index_elements: list[str]
):
    table = model.__table__
    if session.get_bind().dialect.name == "postgresql":
        return (
            pg_insert(table).values(**values).on_conflict_do_nothing(index_elements=index_elements)
        )
    return (
        sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=index_elements)
    )


def _validate_workspace_id(workspace_id: str) -> None:
    try:
        UUID(workspace_id)
    except ValueError as exc:
        raise ValueError("workspace-id must be a UUID") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill safety pipeline state for accounts.")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args(argv)
    try:
        with SessionLocal() as session:
            stats = run_backfill(
                session,
                workspace_id=args.workspace_id,
                batch_size=args.batch_size,
                dry_run=args.dry_run,
                skip_existing=args.skip_existing,
            )
        print(json.dumps(stats.to_dict(), indent=2, sort_keys=True))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"backfill failed: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
