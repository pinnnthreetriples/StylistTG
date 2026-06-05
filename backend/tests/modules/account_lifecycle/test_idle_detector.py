from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Job, JobState, WarmupExecutionMode, WarmupStatus, new_id
from app.modules.account_lifecycle.interfaces import AccountLifecycleState, detect_idle_accounts
from tests.helpers.warmup import seed_warmup_account, seed_warmup_session_raw, seed_warmup_strategy

NOW = datetime(2026, 6, 5, 12, 0, tzinfo=UTC)


def test_detect_idle_accounts_finds_active_account_without_recent_jobs(
    db_session: Session,
) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    db_session.commit()

    result = detect_idle_accounts(
        db_session,
        account.workspace_id,
        threshold_minutes=60,
        now=NOW,
    )

    assert result == [account.id]


def test_detect_idle_accounts_skips_recent_finished_job(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    _job(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        state=JobState.COMPLETED.value,
        finished_at=NOW - timedelta(minutes=10),
    )
    db_session.commit()

    result = detect_idle_accounts(
        db_session,
        account.workspace_id,
        threshold_minutes=60,
        now=NOW,
    )

    assert result == []


def test_detect_idle_accounts_skips_active_job(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    _job(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        state=JobState.RUNNING.value,
        started_at=NOW - timedelta(hours=3),
    )
    db_session.commit()

    result = detect_idle_accounts(
        db_session,
        account.workspace_id,
        threshold_minutes=60,
        now=NOW,
    )

    assert result == []


def test_detect_idle_accounts_skips_active_warmup_session(db_session: Session) -> None:
    account = seed_warmup_account(db_session)
    account.lifecycle_state = AccountLifecycleState.ACTIVE.value
    strategy = seed_warmup_strategy(db_session, execution_mode=WarmupExecutionMode.DRY_RUN.value)
    seed_warmup_session_raw(
        db_session,
        account.id,
        strategy.id,
        WarmupStatus.SCHEDULED.value,
        workspace_id=account.workspace_id,
    )

    result = detect_idle_accounts(
        db_session,
        account.workspace_id,
        threshold_minutes=60,
        now=NOW,
    )

    assert result == []


def _job(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    state: str,
    queued_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> Job:
    job = Job(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account_id,
        job_state=state,
        workflow_type="account_update",
        execution_intent_hash=new_id().replace("-", ""),
        payload_json={},
        plan_json_snapshot={"steps": []},
        queued_at=queued_at,
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(job)
    return job
