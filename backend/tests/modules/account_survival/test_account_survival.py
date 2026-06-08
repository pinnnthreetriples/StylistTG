from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountRuntimeState,
    AccountState,
    AccountSurvivalMetric,
    WarmupExecutionMode,
    new_id,
)
from app.modules.account_survival import events
from app.modules.account_survival.queries import get_account_survival, get_survival_summary
from app.modules.warmup.dispatch_results import _complete_dispatch_session
from app.services.accounts import create_account
from app.services.warmup import create_warmup_session
from tests.helpers.warmup import seed_warmup_strategy

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_account_import_hook_creates_survival_metric(db_session: Session) -> None:
    account = create_account(db_session, external_ref=f"+7999{new_id()[:8]}")

    metric = _metric(db_session, account.id)

    assert metric is not None
    assert metric.workspace_id == account.workspace_id
    assert metric.imported_at is not None
    assert metric.warmup_started_at is None


def test_warmup_start_and_completion_update_existing_metric(
    db_session: Session, monkeypatch
) -> None:
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_min_hours", 12)
    monkeypatch.setattr("app.modules.warmup.cold_soak.settings.warmup_cold_soak_max_hours", 12)
    account = create_account(db_session, external_ref=f"+7999{new_id()[:8]}")
    strategy = seed_warmup_strategy(
        db_session,
        execution_mode=WarmupExecutionMode.DRY_RUN.value,
    )
    _mark_runtime_ready(account)

    warmup_session = create_warmup_session(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=account.workspace_id,
        now=NOW,
    )
    _complete_dispatch_session(db_session, warmup_session, now=NOW + timedelta(days=2))
    db_session.flush()
    metric = _metric(db_session, account.id)

    assert _without_tz(metric.warmup_started_at) == _without_tz(NOW)
    assert _without_tz(metric.warmup_completed_at) == _without_tz(NOW + timedelta(days=2))
    assert metric.warmup_strategy_id == strategy.id


def test_terminal_hook_is_idempotent_for_ban_timestamp(db_session: Session) -> None:
    account = create_account(db_session, external_ref=f"+7999{new_id()[:8]}")
    first_seen = NOW + timedelta(days=1)

    events.on_account_terminal(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        terminal_status="banned",
        now=first_seen,
    )
    events.on_account_terminal(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        terminal_status="banned",
        now=first_seen + timedelta(days=1),
    )
    metric = _metric(db_session, account.id)

    assert _without_tz(metric.banned_at) == _without_tz(first_seen)


def test_survival_summary_and_timeline_read_models(db_session: Session) -> None:
    account = create_account(db_session, external_ref=f"+7999{new_id()[:8]}")
    events.on_warmup_started(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW,
        strategy_id="strategy-1",
        strategy_name="Standard",
    )
    events.on_account_terminal(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        terminal_status="banned",
        now=NOW + timedelta(days=3),
    )
    db_session.flush()

    summary = get_survival_summary(db_session, workspace_id=account.workspace_id)
    timeline = get_account_survival(
        db_session, workspace_id=account.workspace_id, account_id=account.id
    )

    assert summary.total_accounts == 1
    assert summary.banned_count == 1
    assert summary.by_warmup_strategy[0].strategy_name == "Standard"
    assert timeline is not None
    assert _without_tz(timeline.banned_at) == _without_tz(NOW + timedelta(days=3))


def test_empty_workspace_and_missing_metric_return_empty_read_models(
    db_session: Session,
) -> None:
    summary = get_survival_summary(db_session, workspace_id="missing-workspace")
    timeline = get_account_survival(
        db_session,
        workspace_id="missing-workspace",
        account_id="missing-account",
    )

    assert summary.total_accounts == 0
    assert summary.banned_count == 0
    assert summary.by_warmup_strategy == []
    assert timeline is None


def test_freeze_hook_counts_repeated_freezes(db_session: Session) -> None:
    account = create_account(db_session, external_ref=f"+7999{new_id()[:8]}")

    events.on_account_frozen(
        db_session, account_id=account.id, workspace_id=account.workspace_id, now=NOW
    )
    events.on_account_frozen(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        now=NOW + timedelta(hours=1),
    )
    metric = _metric(db_session, account.id)

    assert _without_tz(metric.first_freeze_at) == _without_tz(NOW)
    assert metric.freeze_count == 2


def test_survival_summary_boundary_returns_empty_for_unknown_workspace(
    db_session: Session,
) -> None:
    summary = get_survival_summary(db_session, workspace_id=new_id())

    assert summary.total_accounts == 0
    assert summary.by_warmup_strategy == []


def _mark_runtime_ready(account: Account) -> None:
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state = AccountRuntimeState(
        account_id=account.id,
        session_present=True,
        runtime_health="ready",
        reauth_required=False,
    )


def _without_tz(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None)


def _metric(session: Session, account_id: str) -> AccountSurvivalMetric:
    metric = session.query(AccountSurvivalMetric).filter_by(account_id=account_id).one()
    session.refresh(metric)
    return metric
