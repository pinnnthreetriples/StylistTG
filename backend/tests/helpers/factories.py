from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db import Base

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountOperationCooldown,
    AccountProfileState,
    AccountState,
    Asset,
    AssetKind,
    AssetStatus,
    AuthBatch,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    Job,
    JobState,
    JobStepResult,
    StepStatus,
    User,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
)
from app.services.accounts import create_account
from app.services.database import create_sqlite_test_session_factory
from app.services.jobs import create_profile_job
from app.services.plan import build_profile_plan, compute_execution_intent_hash
from app.services.workspaces import ensure_default_workspace


def make_session():
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    return session_factory, engine


def seed_account(
    session,
    *,
    external_ref: str = "+15550102000",
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    account_state: AccountState = AccountState.REGISTERED,
    runtime_health: str = "unknown",
    session_present: bool = False,
) -> Account:
    account = create_account(session, external_ref=external_ref, workspace_id=workspace_id)
    account.account_state = account_state
    account.runtime_state.runtime_health = runtime_health
    account.runtime_state.session_present = session_present
    session.commit()
    session.refresh(account)
    return account


def seed_account_with_profile(
    session,
    *,
    index: int = 0,
    external_ref: str | None = None,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
) -> Account:
    account = seed_account(
        session,
        external_ref=external_ref or f"+1555010{2000 + index}",
        workspace_id=workspace_id,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    session.add(
        AccountProfileState(
            account_id=account.id,
            telegram_user_id=f"tg-{index}",
            first_name=f"User{index}",
            last_name="Test",
            username=f"user{index}",
            bio="",
        )
    )
    session.commit()
    session.refresh(account)
    return account


def seed_two_workspaces(session):
    ensure_default_workspace(session)
    user = User(
        email="foreign@example.test",
        external_auth_provider="test",
        external_auth_user_id="foreign-user",
        status="active",
    )
    session.add(user)
    session.flush()
    workspace = Workspace(
        name="Foreign Workspace",
        slug="foreign-workspace",
        owner_user_id=user.id,
        status="active",
    )
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    session.add(WorkspacePlan(workspace_id=workspace.id))
    session.commit()
    session.refresh(workspace)
    return DEFAULT_LOCAL_WORKSPACE_ID, workspace.id


def seed_auth_batch(
    session,
    *,
    account_id: str,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    phone_number: str = "+15550102000",
    idempotency_key: str = "test-key-1",
    status: AuthBatchStatus = AuthBatchStatus.RUNNING,
) -> tuple[AuthBatch, AuthBatchItem]:
    batch = AuthBatch(
        workspace_id=workspace_id,
        label="test-batch",
        status=status,
        total_count=1,
        idempotency_key=idempotency_key,
    )
    session.add(batch)
    session.flush()
    item = AuthBatchItem(
        batch_id=batch.id,
        account_id=account_id,
        phone_number=phone_number,
        position=0,
        status=AuthBatchItemStatus.QUEUED,
    )
    session.add(item)
    session.commit()
    session.refresh(batch)
    session.refresh(item)
    return batch, item


def seed_profile_job(
    session,
    *,
    account_id: str,
    payload: dict | None = None,
    state: JobState = JobState.QUEUED,
    finished_at: datetime | None = None,
    failure_reason: str | None = None,
) -> Job:
    payload = payload or {
        "name": "Stylist TG",
        "bio": None,
        "username": None,
        "photo_asset_id": None,
    }
    job = create_profile_job(
        session,
        account_id=account_id,
        payload=payload,
        config=type("Config", (), {"profile_job_cooldown_seconds": 0})(),
    )
    job.job_state = state
    job.finished_at = finished_at
    job.failure_reason = failure_reason
    session.commit()
    session.refresh(job)
    return job


def seed_job(
    session,
    *,
    account_id: str,
    payload: dict,
    state: JobState = JobState.QUEUED,
    job_id: str = "job-1",
    finished_at: datetime | None = None,
    failure_reason: str | None = None,
) -> Job:
    job = Job(
        id=job_id,
        account_id=account_id,
        job_state=state,
        execution_intent_hash=compute_execution_intent_hash(account_id, payload),
        job_payload_version=1,
        payload_json=payload,
        plan_json_snapshot=build_profile_plan(payload),
        queued_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=finished_at,
        failure_reason=failure_reason,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def seed_operation_cooldown(
    session,
    *,
    account_id: str,
    operation: str = "username",
    level: str = "blocked",
    reason_code: str = "recent_flood_wait",
    retry_minutes: int = 5,
    source: str = "job_step_result",
) -> AccountOperationCooldown:
    cooldown = AccountOperationCooldown(
        account_id=account_id,
        operation=operation,
        level=level,
        reason_code=reason_code,
        started_at=datetime.now(UTC),
        retry_after_at=datetime.now(UTC) + timedelta(minutes=retry_minutes),
        source=source,
    )
    session.add(cooldown)
    session.commit()
    return cooldown


def seed_failed_step(
    session,
    *,
    job_id: str,
    step_key: str = "set_username",
    step_type: str = "set_username",
    error_code: str = "FLOOD_WAIT_60",
    error_class: str = "tdlib_error",
    finished_at: datetime | None = None,
) -> JobStepResult:
    step = JobStepResult(
        job_id=job_id,
        step_key=step_key,
        step_type=step_type,
        status=StepStatus.FAILED,
        error_code=error_code,
        error_class=error_class,
        finished_at=finished_at or datetime.now(UTC),
    )
    session.add(step)
    session.commit()
    return step


def seed_asset(
    session,
    *,
    asset_id: str = "asset-1",
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    kind: AssetKind = AssetKind.PROFILE_PHOTO,
) -> Asset:
    asset = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        kind=kind,
        source_path="assets/source/profile.upload",
        normalized_path="assets/normalized/profile.upload",
        content_hash=f"{asset_id}-hash",
        mime="audio/mpeg" if kind == AssetKind.PROFILE_AUDIO else "image/jpeg",
        status=AssetStatus.NORMALIZED,
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset
