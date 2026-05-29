from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.tenant_helpers import require_account_in_workspace
from app.db import get_session
from app.errors import AppError
from app.modules.account_core.presenters import account_list_item_batched
from app.modules.account_core.service import (
    create_account,
    list_accounts as list_accounts_service,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import (
    require_authenticated,
    require_mutation_permission,
)
from app.modules.warmup.service import batch_active_warmups_for_accounts
from app.schemas import (
    AccountCreate,
    AccountListItemRead,
    AccountRead,
)
from app.services.profile_photo_state import batch_latest_profile_photo_asset_ids

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


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
    return [account_list_item_batched(account, warmup_map, photo_map) for account in accounts]


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


__all__ = ["router"]
