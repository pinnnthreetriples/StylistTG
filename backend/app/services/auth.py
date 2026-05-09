from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.tdlib_auth import (
    TdlibAuthAdapter,
    TdlibAuthResult,
    build_tdlib_auth_adapter,
    normalize_phone_number,
)
from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import DEFAULT_LOCAL_WORKSPACE_ID, Account, AccountAuthAttempt, AccountRuntimeState, AccountState, utc_now
from app.services.accounts import create_account, get_account, get_account_by_external_ref
from app.services.profile_sync import ProfileSyncAdapter, build_profile_sync_adapter, sync_account_profile_state


@dataclass(frozen=True)
class AuthMaterializationResult:
    account: Account
    runtime_state: AccountRuntimeState
    status: str
    needs_code: bool
    needs_password: bool = False
    password_hint: str | None = None
    error: str | None = None


class AuthSafetyError(ValueError):
    def __init__(self, *, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


CONTINUABLE_AUTH_STATES = {
    AccountState.AWAITING_CODE,
    AccountState.AWAITING_PASSWORD,
    AccountState.AUTHORIZED_READY,
    AccountState.EXECUTION_USABLE,
}


def start_otp(
    session: Session,
    *,
    phone_number: str,
    adapter: TdlibAuthAdapter | None = None,
    config: Settings = settings,
    workspace_id: str | None = None,
    actor_user_id: str | None = None,
) -> AuthMaterializationResult:
    normalized_phone = normalize_phone_number(phone_number)
    target_workspace_id = workspace_id or DEFAULT_LOCAL_WORKSPACE_ID
    account = get_account_by_external_ref(session, normalized_phone, workspace_id=target_workspace_id)
    if account is None:
        account = create_account(
            session,
            external_ref=normalized_phone,
            workspace_id=target_workspace_id,
            actor_user_id=actor_user_id,
        )
    elif is_account_hard_stopped(account):
        raise AuthSafetyError(
            error_code="AUTH_MANUAL_INTERVENTION_REQUIRED",
            message="account requires manual intervention before a new login attempt",
        )
    elif account.account_state in CONTINUABLE_AUTH_STATES:
        log_event(
            "auth_start_reused",
            account_id=account.id,
            external_ref=mask_external_ref(normalized_phone),
            account_state=account.account_state,
        )
        return auth_result_from_account(account)

    _ensure_production_auth_allowed(config)
    _ensure_start_otp_not_rate_limited(session, account, normalized_phone, config)
    tdlib = adapter or build_tdlib_auth_adapter()
    log_event("auth_start", account_id=account.id, external_ref=mask_external_ref(normalized_phone))
    result = tdlib.start_otp(account.id, normalized_phone)
    record_auth_attempt(
        session,
        account=account,
        external_ref=normalized_phone,
        attempt_kind="start_otp",
        outcome=str(result.status),
    )
    return materialize_auth_result(session, account, result)


def confirm_otp(
    session: Session,
    *,
    account_id: str,
    code: str,
    adapter: TdlibAuthAdapter | None = None,
    profile_sync_adapter: ProfileSyncAdapter | None = None,
) -> AuthMaterializationResult:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    if is_account_hard_stopped(account):
        raise AuthSafetyError(
            error_code="AUTH_MANUAL_INTERVENTION_REQUIRED",
            message="account requires manual intervention before confirming auth",
        )

    tdlib = adapter or build_tdlib_auth_adapter()
    log_event("auth_confirm", account_id=account.id)
    result = tdlib.confirm_otp(account.id, code)
    return materialize_auth_result(
        session,
        account,
        result,
        profile_sync_adapter=profile_sync_adapter,
    )


def get_auth_state(session: Session, account_id: str) -> AuthMaterializationResult:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    return auth_result_from_account(account)


def auth_result_from_account(account: Account) -> AuthMaterializationResult:
    return AuthMaterializationResult(
        account=account,
        runtime_state=account.runtime_state,
        status=account.account_state,
        needs_code=account.account_state == AccountState.AWAITING_CODE,
        needs_password=account.account_state == AccountState.AWAITING_PASSWORD,
    )


def submit_password(
    session: Session,
    *,
    account_id: str,
    password: str,
    adapter: TdlibAuthAdapter | None = None,
    profile_sync_adapter: ProfileSyncAdapter | None = None,
) -> AuthMaterializationResult:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    if is_account_hard_stopped(account):
        raise AuthSafetyError(
            error_code="AUTH_MANUAL_INTERVENTION_REQUIRED",
            message="account requires manual intervention before confirming auth",
        )

    tdlib = adapter or build_tdlib_auth_adapter()
    log_event("auth_password", account_id=account.id)
    result = tdlib.submit_password(account.id, password)
    return materialize_auth_result(
        session,
        account,
        result,
        profile_sync_adapter=profile_sync_adapter,
    )


def materialize_auth_result(
    session: Session,
    account: Account,
    result: TdlibAuthResult,
    *,
    profile_sync_adapter: ProfileSyncAdapter | None = None,
) -> AuthMaterializationResult:
    runtime = account.runtime_state
    account.auth_source = "otp"
    account.account_state = result.account_state
    if result.telegram_user_id:
        account.telegram_user_id = result.telegram_user_id

    runtime.session_present = result.session_present
    runtime.runtime_health = result.runtime_health
    runtime.reauth_required = result.reauth_required
    runtime.recovery_marker = result.recovery_marker
    runtime.updated_at = utc_now()
    if result.telegram_user_id:
        runtime.authorized_last_confirmed_at = utc_now()
    if is_hard_stop_marker(result.recovery_marker):
        account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
        runtime.runtime_health = "manual_intervention_needed"
        runtime.reauth_required = True

    session.commit()
    session.refresh(account)
    session.refresh(runtime)

    if result.account_state in {"authorized_ready", "execution_usable"}:
        try:
            sync_account_profile_state(
                session,
                account.id,
                adapter=profile_sync_adapter or build_profile_sync_adapter(),
            )
            session.refresh(account)
        except Exception as exc:
            session.rollback()
            log_event(
                "profile_sync_skipped",
                account_id=account.id,
                error_class=exc.__class__.__name__,
            )

    return AuthMaterializationResult(
        account=account,
        runtime_state=runtime,
        status=result.status,
        needs_code=result.needs_code,
        needs_password=result.needs_password,
        password_hint=result.password_hint,
        error=result.error,
    )


def is_account_hard_stopped(account: Account) -> bool:
    return (
        account.account_state == AccountState.MANUAL_INTERVENTION_NEEDED
        or is_hard_stop_marker(account.runtime_state.recovery_marker)
    )


def is_hard_stop_marker(marker: str | None) -> bool:
    return bool(marker and marker.startswith("tdlib_hard_stop:"))


def mask_external_ref(external_ref: str) -> str:
    if len(external_ref) <= 4:
        return "***"
    if external_ref.startswith("+") and len(external_ref) >= 8:
        return f"{external_ref[:5]}***{external_ref[-4:]}"
    visible = max(2, min(4, len(external_ref) // 3))
    return f"{external_ref[:visible]}***{external_ref[-visible:]}"


def record_auth_attempt(
    session: Session,
    *,
    account: Account,
    external_ref: str,
    attempt_kind: str,
    outcome: str,
    blocked_reason: str | None = None,
) -> None:
    session.add(
        AccountAuthAttempt(
            account_id=account.id,
            external_ref=external_ref,
            attempt_kind=attempt_kind,
            outcome=outcome,
            blocked_reason=blocked_reason,
            created_at=utc_now(),
        )
    )
    session.commit()


def _ensure_production_auth_allowed(config: Settings) -> None:
    if config.tdlib_use_test_dc or config.tdlib_production_auth_enabled:
        return
    raise AuthSafetyError(
        error_code="PRODUCTION_TDLIB_AUTH_DISABLED",
        message="production TDLib auth is disabled by backend configuration",
    )


def _ensure_start_otp_not_rate_limited(
    session: Session,
    account: Account,
    external_ref: str,
    config: Settings,
) -> None:
    now = utc_now()
    cooldown_started_at = now - timedelta(seconds=max(config.auth_start_cooldown_seconds, 0))
    if config.auth_start_cooldown_seconds > 0:
        recent = session.execute(
            select(AccountAuthAttempt)
            .where(AccountAuthAttempt.account_id == account.id)
            .where(AccountAuthAttempt.attempt_kind == "start_otp")
            .where(AccountAuthAttempt.blocked_reason.is_(None))
            .where(AccountAuthAttempt.created_at >= cooldown_started_at)
            .order_by(AccountAuthAttempt.created_at.desc())
        ).scalars().first()
        if recent is not None:
            raise AuthSafetyError(
                error_code="AUTH_COOLDOWN_ACTIVE",
                message="wait before requesting another Telegram login code",
            )

    day_started_at = now - timedelta(hours=24)
    daily_count = len(
        session.execute(
            select(AccountAuthAttempt.id)
            .where(AccountAuthAttempt.external_ref == external_ref)
            .where(AccountAuthAttempt.attempt_kind == "start_otp")
            .where(AccountAuthAttempt.blocked_reason.is_(None))
            .where(AccountAuthAttempt.created_at >= day_started_at)
        ).scalars().all()
    )
    if daily_count >= config.auth_daily_start_limit:
        raise AuthSafetyError(
            error_code="AUTH_DAILY_LIMIT_REACHED",
            message="daily Telegram login attempt limit reached for this phone number",
        )
