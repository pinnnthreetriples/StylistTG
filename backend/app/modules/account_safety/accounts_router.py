import re

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.adapters.tdlib_readonly_validity import build_tdlib_readonly_validity_adapter
from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.schemas import (
    AccountBatchSafetyPreviewRead,
    AccountBatchSafetyPreviewRequest,
    AccountOperationCooldownRead,
    AccountReadinessRiskRead,
    AccountReadinessRiskSummaryRead,
    AccountSafetyRead,
    AccountSafetyOverrideCreate,
    AccountSafetyOverrideRead,
    AccountSafetySummaryRead,
    AccountValidityCheckRead,
    AccountValidityCheckRequest,
    ActionGateRead,
)
from app.modules.account_safety.action_gate import ACTION_TYPES, evaluate_action_gate
from app.modules.account_safety.batch_preview import build_account_batch_safety_preview
from app.modules.account_safety.gate import (
    AccountSafetyGateAccountNotFound,
    evaluate as evaluate_safety_gate,
)
from app.modules.account_safety.gate_contracts import SafetyGateIntent, SafetyGateVerdict
from app.modules.account_safety.overrides import create_safety_override
from app.modules.account_safety.read_models import (
    build_account_safety,
    build_account_safety_summary,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import (
    require_authenticated,
    require_mutation_permission,
)
from app.services.account_cooldowns import list_active_account_cooldowns
from app.services.account_risk import (
    build_account_readiness_risk,
    build_account_readiness_risk_summary,
)
from app.services.account_validity import list_account_validity_checks, run_account_validity_check
from app.services.runtime_settings import execution_policy_settings

router = APIRouter(prefix="/api/accounts", tags=["accounts"])
ACTION_TYPE_PATTERN = "^(" + "|".join(re.escape(action_type) for action_type in ACTION_TYPES) + ")$"


@router.get("/safety-summary", response_model=list[AccountSafetySummaryRead])
def get_accounts_safety_summary(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return build_account_safety_summary(
        session, workspace_id=auth.workspace_id, config=execution_policy_settings(session)
    )


@router.get("/risk-summary", response_model=AccountReadinessRiskSummaryRead)
def get_accounts_risk_summary(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return build_account_readiness_risk_summary(session, workspace_id=auth.workspace_id)


@router.post("/safety-batch-preview", response_model=AccountBatchSafetyPreviewRead)
def post_accounts_safety_batch_preview(
    payload: AccountBatchSafetyPreviewRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return build_account_batch_safety_preview(
            session,
            account_ids=payload.account_ids,
            operation=payload.operation,
            allow_warning_overrides=payload.allow_warning_overrides,
            workspace_id=auth.workspace_id,
            config=execution_policy_settings(session),
        )
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc


@router.get("/{account_id}/safety", response_model=AccountSafetyRead)
def get_account_safety(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        return build_account_safety(session, account_id, config=execution_policy_settings(session))
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc


@router.get("/{account_id}/cooldowns", response_model=list[AccountOperationCooldownRead])
def get_account_cooldowns(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return [
        AccountOperationCooldownRead(**cooldown)
        for cooldown in list_active_account_cooldowns(session, account_id)
    ]


@router.get("/{account_id}/action-gate", response_model=ActionGateRead)
def get_account_action_gate(
    account_id: str,
    action_type: str = Query(pattern=ACTION_TYPE_PATTERN),
    override_reason: str | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        decision = evaluate_action_gate(
            session,
            workspace_id=auth.workspace_id,
            account_id=account_id,
            action_type=action_type,
            actor_user_id=auth.user_id,
            override_reason=override_reason,
            audit=False,
        )
        return ActionGateRead(**decision)
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
            error_code="ACTION_GATE_INVALID",
            error_class="validation",
            message=message,
        ) from exc


@router.get("/{account_id}/safety-gate", response_model=SafetyGateVerdict)
def get_account_safety_gate(
    account_id: str,
    intent: SafetyGateIntent = Query(...),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        return evaluate_safety_gate(
            session,
            workspace_id=auth.workspace_id,
            account_id=account_id,
            intent=intent,
        )
    except AccountSafetyGateAccountNotFound as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        ) from exc


@router.get("/{account_id}/risk", response_model=AccountReadinessRiskRead)
def get_account_risk(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    account = require_account_in_workspace(session, account_id, auth)
    return build_account_readiness_risk(session, account)


@router.post(
    "/{account_id}/safety-overrides",
    response_model=AccountSafetyOverrideRead,
    status_code=status.HTTP_201_CREATED,
)
def post_account_safety_override(
    account_id: str,
    payload: AccountSafetyOverrideCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        return create_safety_override(
            session,
            account_id,
            workspace_id=auth.workspace_id,
            operation=payload.operation,
            reason=payload.reason,
            requested_blockers=payload.requested_blockers,
        )
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
            error_code="SAFETY_OVERRIDE_REJECTED",
            error_class="safety",
            message=message,
        ) from exc


@router.post("/{account_id}/validity-check", response_model=AccountValidityCheckRead)
def post_account_validity_check(
    account_id: str,
    payload: AccountValidityCheckRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    try:
        adapter = (
            build_tdlib_readonly_validity_adapter() if payload.mode == "tdlib_readonly" else None
        )
        return run_account_validity_check(
            session, account_id, mode=payload.mode, adapter=adapter, workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        message = str(exc)
        if message == "account not found":
            raise AppError(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="ACCOUNT_NOT_FOUND",
                error_class="not_found",
                message=message,
            ) from exc
        if message == "unsupported validity check mode":
            raise AppError(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDITY_CHECK_INVALID_MODE",
                error_class="validation",
                message=message,
            ) from exc
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="VALIDITY_CHECK_FAILED",
            error_class="safety_check",
            message="Account validity check failed",
        ) from exc


@router.get("/{account_id}/validity-checks", response_model=list[AccountValidityCheckRead])
def get_account_validity_checks(
    account_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    require_account_in_workspace(session, account_id, auth)
    return list_account_validity_checks(session, account_id, limit=limit)
