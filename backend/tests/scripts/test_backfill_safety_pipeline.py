from __future__ import annotations

import hashlib

from app.models import Account, AccountBehaviorProfile, AccountGgrScore, NeuroCommentEvent, new_id
import scripts.backfill_safety_pipeline as backfill_module
from scripts.backfill_safety_pipeline import (
    BALANCED_MESSAGE_DELETION_PROBABILITY,
    BALANCED_PROFILE_VIEW_PROBABILITY,
    BALANCED_SCROLL_PROBABILITY,
    BALANCED_TYPING_CPM,
    BALANCED_TYPO_RATE,
    _stable_seed,
    run_backfill,
)
from tests.helpers.factories import seed_account, seed_two_workspaces


def test_dry_run_reports_missing_without_writes(db_session) -> None:
    _seed_accounts(db_session, 2)

    stats = run_backfill(
        db_session,
        workspace_id="00000000-0000-4000-8000-000000000002",
        batch_size=10,
        dry_run=True,
        skip_existing=False,
    )

    assert {
        "accounts_seen": stats.accounts_seen,
        "ggr_created": stats.ggr_created,
        "behavior_created": stats.behavior_created,
        "grace_periods_set": stats.grace_periods_set,
        "ggr_rows": _count(db_session, AccountGgrScore),
        "behavior_rows": _count(db_session, AccountBehaviorProfile),
        "event_rows": _count(db_session, NeuroCommentEvent),
    } == {
        "accounts_seen": 2,
        "ggr_created": 2,
        "behavior_created": 2,
        "grace_periods_set": 2,
        "ggr_rows": 0,
        "behavior_rows": 0,
        "event_rows": 0,
    }


def test_backfill_creates_missing_rows(db_session) -> None:
    account = _seed_accounts(db_session, 1)[0]

    stats = run_backfill(
        db_session,
        workspace_id=account.workspace_id,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    ggr = db_session.query(AccountGgrScore).one()
    behavior = db_session.query(AccountBehaviorProfile).one()
    db_session.refresh(account)
    assert {
        "ggr": (ggr.score, ggr.bucket, ggr.breakdown_json, ggr.last_calculated_at),
        "behavior": (
            behavior.typing_speed_baseline_cpm,
            behavior.typo_rate_baseline,
            behavior.profile_view_probability_baseline,
            behavior.scroll_probability_baseline,
            behavior.message_deletion_probability_baseline,
            behavior.action_sequence_seed,
        ),
        "grace_set": account.safety_grace_period_until is not None,
        "events": stats.events_created,
    } == {
        "ggr": (5.0, "medium", {}, None),
        "behavior": (
            BALANCED_TYPING_CPM,
            BALANCED_TYPO_RATE,
            BALANCED_PROFILE_VIEW_PROBABILITY,
            BALANCED_SCROLL_PROBABILITY,
            BALANCED_MESSAGE_DELETION_PROBABILITY,
            _stable_seed(account.id),
        ),
        "grace_set": True,
        "events": 1,
    }


def test_backfill_is_idempotent_for_artifact_rows(db_session) -> None:
    account = _seed_accounts(db_session, 1)[0]
    run_backfill(
        db_session,
        workspace_id=account.workspace_id,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    second = run_backfill(
        db_session,
        workspace_id=account.workspace_id,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    assert {
        "second_ggr": second.ggr_created,
        "second_behavior": second.behavior_created,
        "ggr_rows": _count(db_session, AccountGgrScore),
        "behavior_rows": _count(db_session, AccountBehaviorProfile),
        "event_rows": _count(db_session, NeuroCommentEvent),
    } == {
        "second_ggr": 0,
        "second_behavior": 0,
        "ggr_rows": 1,
        "behavior_rows": 1,
        "event_rows": 1,
    }


def test_backfill_upsert_ignores_stale_duplicate_plan(db_session, monkeypatch) -> None:
    account = _seed_accounts(db_session, 1)[0]
    run_backfill(
        db_session,
        workspace_id=account.workspace_id,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    monkeypatch.setattr(
        backfill_module,
        "_planned_actions",
        lambda _session, _account: {"ggr_created", "behavior_created"},
    )

    second = run_backfill(
        db_session,
        workspace_id=account.workspace_id,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    assert {
        "second_ggr": second.ggr_created,
        "second_behavior": second.behavior_created,
        "second_events": second.events_created,
        "ggr_rows": _count(db_session, AccountGgrScore),
        "behavior_rows": _count(db_session, AccountBehaviorProfile),
        "event_rows": _count(db_session, NeuroCommentEvent),
    } == {
        "second_ggr": 0,
        "second_behavior": 0,
        "second_events": 0,
        "ggr_rows": 1,
        "behavior_rows": 1,
        "event_rows": 1,
    }


def test_stable_seed_uses_sha256_not_python_hash() -> None:
    account_id = "00000000-0000-4000-8000-000000000123"
    expected = int(hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:8], 16) % (2**31)

    assert _stable_seed(account_id) == expected


def test_backfill_skips_existing_partial_data(db_session) -> None:
    account_a, account_b = _seed_accounts(db_session, 2)
    db_session.add(_ggr(account_a))
    db_session.add(_behavior(account_b))
    db_session.commit()

    stats = run_backfill(
        db_session,
        workspace_id=account_a.workspace_id,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    assert {
        "ggr_created": stats.ggr_created,
        "behavior_created": stats.behavior_created,
        "ggr_rows": _count(db_session, AccountGgrScore),
        "behavior_rows": _count(db_session, AccountBehaviorProfile),
    } == {
        "ggr_created": 1,
        "behavior_created": 1,
        "ggr_rows": 2,
        "behavior_rows": 2,
    }


def test_backfill_commits_per_batch(db_session, monkeypatch) -> None:
    _seed_accounts(db_session, 10)
    original_commit = db_session.commit
    commit_count = 0

    def counted_commit() -> None:
        nonlocal commit_count
        commit_count += 1
        original_commit()

    monkeypatch.setattr(db_session, "commit", counted_commit)

    stats = run_backfill(
        db_session,
        workspace_id="00000000-0000-4000-8000-000000000002",
        batch_size=3,
        dry_run=False,
        skip_existing=False,
    )

    assert {"commits": commit_count, "batches": stats.batches_committed} == {
        "commits": 4,
        "batches": 4,
    }


def test_backfill_workspace_filter_does_not_touch_foreign_workspace(db_session) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    seed_account(db_session, external_ref="+15550106001", workspace_id=workspace_a)
    seed_account(db_session, external_ref="+15550106002", workspace_id=workspace_b)

    run_backfill(
        db_session,
        workspace_id=workspace_a,
        batch_size=10,
        dry_run=False,
        skip_existing=False,
    )

    assert {
        "a_ggr": _count(db_session, AccountGgrScore, workspace_a),
        "b_ggr": _count(db_session, AccountGgrScore, workspace_b),
        "a_behavior": _count(db_session, AccountBehaviorProfile, workspace_a),
        "b_behavior": _count(db_session, AccountBehaviorProfile, workspace_b),
    } == {"a_ggr": 1, "b_ggr": 0, "a_behavior": 1, "b_behavior": 0}


def _seed_accounts(db_session, count: int):
    return [
        seed_account(db_session, external_ref=f"+15550105{index:03d}") for index in range(count)
    ]


def _count(db_session, model, workspace_id: str | None = None) -> int:
    query = db_session.query(model)
    if workspace_id is not None:
        query = query.filter(model.workspace_id == workspace_id)
    return query.count()


def _ggr(account: Account) -> AccountGgrScore:
    return AccountGgrScore(
        id=new_id(),
        workspace_id=account.workspace_id,
        account_id=account.id,
        score=8.0,
        bucket="strong",
        breakdown_json={},
    )


def _behavior(account: Account) -> AccountBehaviorProfile:
    return AccountBehaviorProfile(
        id=new_id(),
        workspace_id=account.workspace_id,
        account_id=account.id,
        typing_speed_baseline_cpm=100,
        typo_rate_baseline=0.01,
        profile_view_probability_baseline=0.1,
        scroll_probability_baseline=0.1,
        message_deletion_probability_baseline=0.01,
        action_sequence_seed=1,
    )
