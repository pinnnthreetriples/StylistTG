from __future__ import annotations

import base64
import binascii
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.errors import AppError
from app.modules.account_imports.service import (
    confirm_import_batch,
    create_import_batch,
    get_import_batch,
    import_batch_to_dict,
    list_import_batches,
    validate_batch,
)
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.schemas import (
    AccountImportBatchConfirm,
    AccountImportBatchCreate,
    AccountImportBatchRead,
    AccountImportBatchValidate,
)

router = APIRouter(prefix="/api/account-import-batches", tags=["account-import-batches"])


@router.post("", response_model=AccountImportBatchRead, status_code=201)
def post_import_batch(
    payload: AccountImportBatchCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    row = create_import_batch(
        session,
        workspace_id=auth.workspace_id,
        actor_user_id=auth.user_id,
        source_type=payload.source_type,
        label=payload.label,
        dry_run=payload.dry_run,
        metadata=payload.metadata,
    )
    return AccountImportBatchRead(**import_batch_to_dict(row))


@router.get("", response_model=list[AccountImportBatchRead])
def get_import_batches(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    return [
        AccountImportBatchRead(**import_batch_to_dict(row))
        for row in list_import_batches(session, workspace_id=auth.workspace_id)
    ]


@router.get("/{batch_id}", response_model=AccountImportBatchRead)
def get_import_batch_detail(
    batch_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    row = get_import_batch(session, batch_id=str(batch_id), workspace_id=auth.workspace_id)
    if row is None:
        raise AppError(
            status_code=404,
            error_code="IMPORT_BATCH_NOT_FOUND",
            error_class="not_found",
            message="import batch not found",
        )
    return AccountImportBatchRead(**import_batch_to_dict(row))


@router.post("/{batch_id}/validate", response_model=AccountImportBatchRead)
def post_validate_import_batch(
    batch_id: UUID,
    payload: AccountImportBatchValidate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    content = _decode_optional_base64(payload.content_base64)
    row = validate_batch(
        session,
        batch_id=str(batch_id),
        workspace_id=auth.workspace_id,
        content=content,
        metadata=payload.metadata,
    )
    return AccountImportBatchRead(**import_batch_to_dict(row))


@router.post("/{batch_id}/confirm", response_model=AccountImportBatchRead)
def post_confirm_import_batch(
    batch_id: UUID,
    payload: AccountImportBatchConfirm,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    row = confirm_import_batch(
        session,
        batch_id=str(batch_id),
        workspace_id=auth.workspace_id,
        confirmation=payload.confirmation,
    )
    return AccountImportBatchRead(**import_batch_to_dict(row))


def _decode_optional_base64(value: str | None) -> bytes | None:
    if value is None:
        return None
    max_encoded_len = ((settings.account_import_max_upload_bytes + 2) // 3) * 4
    if len(value) > max_encoded_len:
        raise AppError(
            status_code=413,
            error_code="IMPORT_CONTENT_TOO_LARGE",
            error_class="validation",
            message="content_base64 is too large",
        )
    try:
        decoded = base64.b64decode(value, validate=True)
    except binascii.Error as exc:
        raise AppError(
            status_code=400,
            error_code="IMPORT_CONTENT_INVALID",
            error_class="validation",
            message="content_base64 is invalid",
        ) from exc
    if len(decoded) > settings.account_import_max_upload_bytes:
        raise AppError(
            status_code=413,
            error_code="IMPORT_CONTENT_TOO_LARGE",
            error_class="validation",
            message="content_base64 is too large",
        )
    return decoded


__all__ = ["router"]
