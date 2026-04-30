from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.account_context import account_id_header
from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.db import get_session
from app.errors import AppError
from app.logging_utils import log_event
from app.models import Account
from app.schemas import (
    AccountCreate,
    AccountListItemRead,
    AccountRead,
    AccountRuntimeDiagnosticsRead,
    AccountSafetyRead,
    AccountSafetySummaryRead,
    AccountValidityCheckRead,
    AccountValidityCheckRequest,
    AuthStateRead,
    JobSummaryRead,
    RuntimeRefreshRead,
)
from app.services.execution_policy import ensure_execution_usable
from app.services.profile_photo_state import latest_applied_profile_photo_asset_id
from app.services.profile_sync import (
    build_profile_sync_adapter,
    sync_account_profile_snapshot,
)
from app.services.runtime_diagnostics import account_runtime_diagnostics
from app.services.account_safety import build_account_safety, build_account_safety_summary
from app.services.account_validity import list_account_validity_checks, run_account_validity_check
from app.services.accounts import create_account, delete_account, get_account, list_accounts as list_accounts_service
from app.services.dashboard import job_summary
from app.services.jobs import get_latest_account_job, list_account_jobs

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def post_account(payload: AccountCreate, session: Session = Depends(get_session)):
    return create_account(
        session,
        external_ref=payload.external_ref,
        telegram_user_id=payload.telegram_user_id,
    )


@router.get("", response_model=list[AccountListItemRead])
def get_accounts(session: Session = Depends(get_session)):
    return [_account_list_item(session, account) for account in list_accounts_service(session)]


@router.get("/safety-summary", response_model=list[AccountSafetySummaryRead])
def get_accounts_safety_summary(session: Session = Depends(get_session)):
    return build_account_safety_summary(session)


@router.get("/auth-state", response_model=AuthStateRead)
def get_account_auth_state_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    from app.api.auth import get_account_auth_state

    return get_account_auth_state(account_id, session)


@router.post("/refresh-runtime", response_model=RuntimeRefreshRead)
def refresh_runtime_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    return refresh_runtime(account_id, session)


@router.get("/runtime-diagnostics", response_model=AccountRuntimeDiagnosticsRead)
def runtime_diagnostics_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    return runtime_diagnostics(account_id, session)


@router.get("/jobs", response_model=list[JobSummaryRead])
def list_jobs_from_header(
    account_id: str = Depends(account_id_header),
    limit: int = 10,
    session: Session = Depends(get_session),
):
    return list_jobs(account_id, limit, session)


@router.get("/jobs/latest", response_model=JobSummaryRead)
def latest_job_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    return latest_job(account_id, session)


@router.get("/{account_id}", response_model=AccountRead)
def get_account_endpoint(account_id: str, session: Session = Depends(get_session)):
    account = get_account(session, account_id)
    if account is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        )
    return account


@router.get("/{account_id}/safety", response_model=AccountSafetyRead)
def get_account_safety(account_id: str, session: Session = Depends(get_session)):
    try:
        return build_account_safety(session, account_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc


@router.post("/{account_id}/validity-check", response_model=AccountValidityCheckRead)
def post_account_validity_check(
    account_id: str,
    payload: AccountValidityCheckRequest,
    session: Session = Depends(get_session),
):
    try:
        return run_account_validity_check(session, account_id, mode=payload.mode)
    except ValueError as exc:
        message = str(exc)
        if message == "account not found":
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="ACCOUNT_NOT_FOUND",
                error_class="not_found",
                message=message,
            ) from exc
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDITY_CHECK_INVALID_MODE",
            error_class="validation",
            message=message,
        ) from exc


@router.get("/{account_id}/validity-checks", response_model=list[AccountValidityCheckRead])
def get_account_validity_checks(
    account_id: str,
    limit: int = 10,
    session: Session = Depends(get_session),
):
    if get_account(session, account_id) is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        )
    return list_account_validity_checks(session, account_id, limit=limit)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account_endpoint(account_id: str, session: Session = Depends(get_session)):
    try:
        delete_account(session, account_id)
    except ValueError as exc:
        message = str(exc)
        if message == "account not found":
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="ACCOUNT_NOT_FOUND",
                error_class="not_found",
                message=message,
            ) from exc
        if message == "active job cannot be deleted":
            raise AppError(
                status_code=status.HTTP_409_CONFLICT,
                error_code="ACCOUNT_ACTIVE_JOB_CANNOT_DELETE",
                error_class="account_state",
                message=message,
            ) from exc
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="ACCOUNT_DELETE_FAILED",
            error_class="account_state",
            message=message,
        ) from exc


@router.post("/{account_id}/refresh-runtime", response_model=RuntimeRefreshRead)
def refresh_runtime(account_id: str, session: Session = Depends(get_session)):
    try:
        log_event("runtime_refresh_requested", account_id=account_id)
        result = ensure_execution_usable(
            session,
            account_id,
            adapter=build_profile_execution_adapter(),
        )
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    if result.account.account_state == "execution_usable":
        profile_sync_adapter = build_profile_sync_adapter()
        try:
            sync_account_profile_snapshot(session, account_id, adapter=profile_sync_adapter)
        except Exception as exc:
            session.rollback()
            log_event(
                "profile_sync_failed",
                account_id=account_id,
                error_class=exc.__class__.__name__,
            )
            raise AppError(
                status_code=status.HTTP_502_BAD_GATEWAY,
                error_code="PROFILE_SYNC_FAILED",
                error_class="telegram_sync",
                message="Telegram profile sync failed",
                details={"reason": exc.__class__.__name__},
            ) from exc
    diagnostics = account_runtime_diagnostics(session, account_id)
    return RuntimeRefreshRead(
        account_id=result.account.id,
        account_state=result.account.account_state,
        runtime_health=result.runtime_state.runtime_health,
        is_execution_usable=result.account.account_state == "execution_usable",
        last_error_code=diagnostics["last_error_code"],
        last_error_class=diagnostics["last_error_class"],
        refreshed_at=datetime.now(UTC),
    )


@router.get("/{account_id}/runtime-diagnostics", response_model=AccountRuntimeDiagnosticsRead)
def runtime_diagnostics(account_id: str, session: Session = Depends(get_session)):
    try:
        payload = account_runtime_diagnostics(session, account_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
    return AccountRuntimeDiagnosticsRead(**payload)


@router.get("/{account_id}/jobs", response_model=list[JobSummaryRead])
def list_jobs(account_id: str, limit: int = 10, session: Session = Depends(get_session)):
    account = get_account(session, account_id)
    if account is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        )
    return [JobSummaryRead(**job_summary(job)) for job in list_account_jobs(session, account_id, limit=limit)]


@router.get("/{account_id}/jobs/latest", response_model=JobSummaryRead)
def latest_job(account_id: str, session: Session = Depends(get_session)):
    account = get_account(session, account_id)
    if account is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        )
    job = get_latest_account_job(session, account_id)
    if job is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="JOB_NOT_FOUND",
            error_class="not_found",
            message="job not found",
        )
    return JobSummaryRead(**job_summary(job))


def _account_list_item(session: Session, account: Account) -> AccountListItemRead:
    profile = account.profile_state
    first_name = profile.first_name if profile else None
    last_name = profile.last_name if profile else None
    display_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    username = profile.username if profile else None
    runtime = account.runtime_state
    return AccountListItemRead(
        account_id=account.id,
        display_name=display_name,
        username=username,
        phone_number=account.external_ref,
        telegram_user_id=account.telegram_user_id,
        account_state=account.account_state,
        runtime_health=runtime.runtime_health,
        is_execution_usable=account.account_state == "execution_usable",
        is_test_dc=_is_test_dc_account(account),
        profile_photo_asset_id=latest_applied_profile_photo_asset_id(session, account.id),
        updated_at=account.updated_at,
    )


def _is_test_dc_account(account: Account) -> bool:
    return account.external_ref.startswith("+999") or account.telegram_user_id == "mock-user"
