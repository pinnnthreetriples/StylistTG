from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.adapters.tdlib_auth import build_tdlib_auth_adapter
from app.db import get_session
from app.errors import AppError
from app.schemas import (
    AuthRuntimeModeRead,
    AuthRuntimeModeUpdate,
    AuthStateRead,
    OtpConfirmRequest,
    OtpStartRequest,
    PasswordSubmitRequest,
)
from app.services.auth import (
    AuthMaterializationResult,
    AuthSafetyError,
    confirm_otp,
    get_auth_state,
    start_otp,
    submit_password,
)
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
    require_role,
)
from app.api.tenant_helpers import require_account_in_workspace
from app.services.runtime_settings import (
    auth_runtime_settings,
    get_auth_runtime_mode as get_auth_runtime_mode_values,
    update_auth_runtime_mode,
)

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/auth/runtime-mode", response_model=AuthRuntimeModeRead)
def get_auth_runtime_mode(
    session: Session = Depends(get_session),
    _auth: AuthContext = Depends(require_authenticated),
):
    return AuthRuntimeModeRead(**get_auth_runtime_mode_values(session))


@router.patch("/auth/runtime-mode", response_model=AuthRuntimeModeRead)
def patch_auth_runtime_mode(
    payload: AuthRuntimeModeUpdate,
    session: Session = Depends(get_session),
    _auth: AuthContext = Depends(require_role("admin")),
):
    return AuthRuntimeModeRead(
        **update_auth_runtime_mode(session, tdlib_use_test_dc=payload.tdlib_use_test_dc)
    )


@router.post("/auth/otp/start", response_model=AuthStateRead, status_code=status.HTTP_201_CREATED)
def post_otp_start(
    payload: OtpStartRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        result = start_otp(
            session,
            phone_number=payload.phone_number,
            adapter=build_tdlib_auth_adapter(),
            config=auth_runtime_settings(session),
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
    except AuthSafetyError as exc:
        raise _auth_safety_app_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _auth_response(result)


@router.post("/auth/otp/confirm", response_model=AuthStateRead)
def post_otp_confirm(
    payload: OtpConfirmRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, payload.account_id, auth)
    try:
        result = confirm_otp(
            session,
            account_id=payload.account_id,
            code=payload.code,
            adapter=build_tdlib_auth_adapter(),
            workspace_id=auth.workspace_id,
        )
    except AuthSafetyError as exc:
        raise _auth_safety_app_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _auth_response(result)


@router.post("/auth/password", response_model=AuthStateRead)
def post_password(
    payload: PasswordSubmitRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, payload.account_id, auth)
    try:
        result = submit_password(
            session,
            account_id=payload.account_id,
            password=payload.password,
            adapter=build_tdlib_auth_adapter(),
            workspace_id=auth.workspace_id,
        )
    except AuthSafetyError as exc:
        raise _auth_safety_app_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _auth_response(result)


@router.get("/accounts/{account_id}/auth-state", response_model=AuthStateRead)
def get_account_auth_state(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        result = get_auth_state(session, account_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _auth_response(result)


def _auth_response(result: AuthMaterializationResult) -> AuthStateRead:
    return AuthStateRead(
        account_id=result.account.id,
        external_ref=result.account.external_ref,
        telegram_user_id=result.account.telegram_user_id,
        orchestration_state=result.account.account_state,
        auth_step_status=result.status,
        needs_code=result.needs_code,
        needs_password=result.needs_password,
        password_hint=result.password_hint,
        session_present=result.runtime_state.session_present,
        runtime_health=result.runtime_state.runtime_health,
        reauth_required=result.runtime_state.reauth_required,
        recovery_marker=result.runtime_state.recovery_marker,
        authorized_last_confirmed_at=result.runtime_state.authorized_last_confirmed_at,
        error=result.error,
    )


auth_response = _auth_response


def _auth_safety_app_error(exc: AuthSafetyError) -> AppError:
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    if exc.error_code in {
        "AUTH_MANUAL_INTERVENTION_REQUIRED",
        "PRODUCTION_TDLIB_AUTH_DISABLED",
    }:
        status_code = status.HTTP_409_CONFLICT
    return AppError(
        status_code=status_code,
        error_code=exc.error_code,
        error_class="auth_safety",
        message=exc.message,
    )
