from typing import Literal, cast

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.models import Account, WarmupSession
from app.schemas import (
    AccountCreate,
    AccountListItemRead,
    AccountRead,
    AccountWarmupInfoRead,
)
from app.services.accounts import create_account, list_accounts as list_accounts_service
from app.services.auth_context import (
    AuthContext,
    require_authenticated,
    require_mutation_permission,
)
from app.services.profile_photo_state import (
    batch_latest_profile_photo_asset_ids,
    latest_applied_profile_photo_asset_id,
)
from app.services.warmup import batch_active_warmups_for_accounts, warmup_operation_policy

router = APIRouter(prefix="/api/accounts", tags=["accounts"])
AccountOrigin = Literal["imported", "bought", "created"]


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def post_account(
    payload: AccountCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        return create_account(
            session,
            external_ref=payload.external_ref,
            telegram_user_id=payload.telegram_user_id,
            origin=payload.origin,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_409_CONFLICT,
            error_code="ACCOUNT_ALREADY_EXISTS",
            error_class="conflict",
            message=str(exc),
        ) from exc


@router.get("", response_model=list[AccountListItemRead])
def get_accounts(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    accounts = list_accounts_service(session, workspace_id=auth.workspace_id)
    account_ids = [a.id for a in accounts]
    warmup_map = batch_active_warmups_for_accounts(
        session,
        account_ids=account_ids,
        workspace_id=auth.workspace_id,
    )
    photo_map = batch_latest_profile_photo_asset_ids(session, account_ids)
    return [_account_list_item_batched(account, warmup_map, photo_map) for account in accounts]


@router.get("/{account_id}", response_model=AccountRead)
def get_account_endpoint(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    account = require_account_in_workspace(session, account_id, auth)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account_endpoint(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    require_account_in_workspace(session, account_id, auth)
    raise AppError(
        status_code=status.HTTP_409_CONFLICT,
        error_code="ACCOUNT_DELETE_REQUIRES_REQUEST",
        error_class="account_lifecycle",
        message="account deletion requires deletion preview and confirmed deletion request",
    )


def account_list_item(session: Session, account: Account) -> AccountListItemRead:
    profile = account.profile_state
    first_name = profile.first_name if profile else None
    last_name = profile.last_name if profile else None
    display_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    username = profile.username if profile else None
    runtime = account.runtime_state
    warmup_policy = warmup_operation_policy(
        session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        operation="profile_update",
    )
    return AccountListItemRead(
        account_id=account.id,
        display_name=display_name,
        username=username,
        phone_number=account.external_ref,
        telegram_user_id=account.telegram_user_id,
        origin=_account_origin(account),
        account_state=account.account_state,
        runtime_health=runtime.runtime_health,
        is_execution_usable=account.account_state == "execution_usable",
        is_test_dc=_is_test_dc_account(account),
        profile_photo_asset_id=latest_applied_profile_photo_asset_id(session, account.id),
        updated_at=account.updated_at,
        warmup=AccountWarmupInfoRead(
            session_id=warmup_policy["session_id"],
            status=warmup_policy["status"],
            current_day=warmup_policy["current_day"],
            is_locked=warmup_policy["is_locked"],
        )
        if warmup_policy["session_id"]
        else None,
    )


def _account_list_item_batched(
    account: Account,
    warmup_map: dict[str, WarmupSession],
    photo_map: dict[str, str | None],
) -> AccountListItemRead:
    profile = account.profile_state
    first_name = profile.first_name if profile else None
    last_name = profile.last_name if profile else None
    display_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    username = profile.username if profile else None
    runtime = account.runtime_state
    warmup_session = warmup_map.get(account.id)
    locked_operations = {"profile_update", "proxy_change", "account_delete"}
    is_locked = warmup_session is not None and "profile_update" in locked_operations
    warmup_info: AccountWarmupInfoRead | None = None
    if warmup_session is not None:
        warmup_info = AccountWarmupInfoRead(
            session_id=warmup_session.id,  # type: ignore[union-attr]
            status=warmup_session.status,  # type: ignore[union-attr]
            current_day=warmup_session.current_day,  # type: ignore[union-attr]
            is_locked=is_locked,
        )
    return AccountListItemRead(
        account_id=account.id,
        display_name=display_name,
        username=username,
        phone_number=account.external_ref,
        telegram_user_id=account.telegram_user_id,
        origin=_account_origin(account),
        account_state=account.account_state,
        runtime_health=runtime.runtime_health,
        is_execution_usable=account.account_state == "execution_usable",
        is_test_dc=_is_test_dc_account(account),
        profile_photo_asset_id=photo_map.get(account.id),
        updated_at=account.updated_at,
        warmup=warmup_info,
    )


def _is_test_dc_account(account: Account) -> bool:
    return account.external_ref.startswith("+999") or account.telegram_user_id == "mock-user"


def _account_origin(account: Account) -> AccountOrigin:
    return cast(AccountOrigin, account.origin)
