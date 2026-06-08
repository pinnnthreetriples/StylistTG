from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.modules.account_lifecycle.contracts import (
    AccountDeletionPreviewRead,
    AccountDeletionRequestCreate,
    AccountDeletionRequestRead,
    AccountExportRequestRead,
    AccountLifecycleRead,
)
from app.modules.account_lifecycle.service import (
    build_account_deletion_preview,
    create_account_export_request,
    deletion_request_to_dict,
    export_request_to_dict,
    get_account_lifecycle,
    get_deletion_request,
    get_export_request,
    list_deletion_requests,
    list_export_requests,
    request_account_deletion,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import (
    require_authenticated,
    require_mutation_permission,
)

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _account_not_found_error(exc: ValueError | None = None) -> AppError:
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND,
        error_code="ACCOUNT_NOT_FOUND",
        error_class="not_found",
        message=str(exc),
    )


@router.get("/{account_id}/lifecycle", response_model=AccountLifecycleRead)
def get_account_lifecycle_state(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return AccountLifecycleRead(
            **get_account_lifecycle(session, account_id=account_id, workspace_id=auth.workspace_id)
        )
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc


@router.get("/{account_id}/deletion-preview", response_model=AccountDeletionPreviewRead)
def get_account_deletion_preview(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return AccountDeletionPreviewRead(
            **build_account_deletion_preview(
                session, account_id=account_id, workspace_id=auth.workspace_id
            )
        )
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc


@router.post(
    "/{account_id}/deletion-requests",
    response_model=AccountDeletionRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def post_account_deletion_request(
    account_id: str,
    payload: AccountDeletionRequestCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        request = request_account_deletion(
            session,
            account_id=account_id,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
            reason=payload.reason,
            confirmation=payload.confirmation,
            dry_run=payload.dry_run,
        )
        return AccountDeletionRequestRead(**deletion_request_to_dict(request))
    except ValueError as exc:
        message = str(exc)
        if message == "account not found":
            raise _account_not_found_error(exc) from exc
        raise AppError(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="ACCOUNT_DELETION_REJECTED",
            error_class="account_lifecycle",
            message=message,
        ) from exc


@router.get("/{account_id}/deletion-requests", response_model=list[AccountDeletionRequestRead])
def get_account_deletion_requests(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return [
            AccountDeletionRequestRead(**deletion_request_to_dict(request))
            for request in list_deletion_requests(
                session, account_id=account_id, workspace_id=auth.workspace_id
            )
        ]
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc


@router.get(
    "/{account_id}/deletion-requests/{request_id}", response_model=AccountDeletionRequestRead
)
def get_account_deletion_request(
    account_id: str,
    request_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        request = get_deletion_request(
            session, account_id=account_id, request_id=request_id, workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc
    if request is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="DELETION_REQUEST_NOT_FOUND",
            error_class="not_found",
            message="deletion request not found",
        )
    return AccountDeletionRequestRead(**deletion_request_to_dict(request))


@router.post(
    "/{account_id}/export-requests",
    response_model=AccountExportRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def post_account_export_request(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        request = create_account_export_request(
            session,
            account_id=account_id,
            workspace_id=auth.workspace_id,
            actor_user_id=auth.user_id,
        )
        return AccountExportRequestRead(**export_request_to_dict(request))
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc


@router.get("/{account_id}/export-requests", response_model=list[AccountExportRequestRead])
def get_account_export_requests(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return [
            AccountExportRequestRead(**export_request_to_dict(request))
            for request in list_export_requests(
                session, account_id=account_id, workspace_id=auth.workspace_id
            )
        ]
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc


@router.get("/{account_id}/export-requests/{request_id}", response_model=AccountExportRequestRead)
def get_account_export_request(
    account_id: str,
    request_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        request = get_export_request(
            session, account_id=account_id, request_id=request_id, workspace_id=auth.workspace_id
        )
    except ValueError as exc:
        raise _account_not_found_error(exc) from exc
    if request is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="EXPORT_REQUEST_NOT_FOUND",
            error_class="not_found",
            message="export request not found",
        )
    return AccountExportRequestRead(**export_request_to_dict(request))
