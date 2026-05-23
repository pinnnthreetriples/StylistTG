from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import timedelta
import json
import socket
from uuid import UUID

from sqlalchemy import select
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
            if "ggr_created" in actions:
                stats.ggr_created += 1
            if "behavior_created" in actions:
                stats.behavior_created += 1
            if "origin_set" in actions:
                stats.origins_set += 1
            if "grace_period_set" in actions:
                stats.grace_periods_set += 1
            if dry_run or not actions:
                continue
            _apply_actions(session, account, actions, stats=stats, executed_by=actor)
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
) -> None:
    now = utc_now()
    if "ggr_created" in actions:
        session.add(
            AccountGgrScore(
                id=new_id(),
                workspace_id=account.workspace_id,
                account_id=account.id,
                score=5.0,
                bucket="medium",
                breakdown_json={},
                previous_score=None,
                last_calculated_at=None,
                next_calculation_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    if "behavior_created" in actions:
        session.add(
            AccountBehaviorProfile(
                id=new_id(),
                workspace_id=account.workspace_id,
                account_id=account.id,
                typing_speed_baseline_cpm=BALANCED_TYPING_CPM,
                typo_rate_baseline=BALANCED_TYPO_RATE,
                profile_view_probability_baseline=BALANCED_PROFILE_VIEW_PROBABILITY,
                scroll_probability_baseline=BALANCED_SCROLL_PROBABILITY,
                message_deletion_probability_baseline=BALANCED_MESSAGE_DELETION_PROBABILITY,
                action_sequence_seed=_stable_seed(account.id),
                created_at=now,
                updated_at=now,
            )
        )
    if "origin_set" in actions:
        account.origin = "imported"
    if "grace_period_set" in actions:
        account.safety_grace_period_until = now + timedelta(days=GRACE_PERIOD_DAYS)
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
                "actions_taken": sorted(actions),
                "dry_run": stats.dry_run,
                "executed_by": executed_by,
            },
            created_at=now,
        )
    )
    stats.events_created += 1


def _stable_seed(account_id: str) -> int:
    return hash(account_id) % (2**31)


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
        print(str(exc))
        return 1
    except Exception as exc:
        print(f"backfill failed: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
