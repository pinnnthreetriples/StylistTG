from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.modules.account_core.context import account_id_header as _account_id_header
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_authenticated, require_mutation_permission
from app.modules.story.contracts import StoryDraftCreate, StoryDraftRead, StoryDraftUpdate
from app.modules.story.drafts import (
    create_story_draft,
    delete_story_draft,
    list_story_drafts,
    update_story_draft,
)

router = APIRouter(prefix="/api/story-drafts", tags=["story-drafts"])


def account_id_header(x_account_id: str = Header(alias="X-Account-Id")) -> str:
    return _account_id_header(x_account_id)


@router.get("/{account_id}", response_model=list[StoryDraftRead])
def get_story_drafts(
    account_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return list_story_drafts(session, account_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


@router.get("", response_model=list[StoryDraftRead])
def get_story_drafts_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    try:
        return list_story_drafts(session, account_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


@router.post("", response_model=StoryDraftRead, status_code=status.HTTP_201_CREATED)
def post_story_draft(
    payload: StoryDraftCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        return create_story_draft(session, payload.model_dump(), workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


@router.patch("/{draft_id}", response_model=StoryDraftRead)
def patch_story_draft(
    draft_id: str,
    payload: StoryDraftUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        return update_story_draft(
            session,
            draft_id,
            payload.model_dump(exclude_none=True),
            workspace_id=auth.workspace_id,
        )
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_story_draft(
    draft_id: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
):
    try:
        delete_story_draft(session, draft_id, workspace_id=auth.workspace_id)
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


def _story_draft_error(exc: ValueError) -> AppError:
    message = str(exc)
    error_code = "ACCOUNT_NOT_FOUND" if message == "account not found" else "VALIDATION_ERROR"
    error_class = (
        "not_found" if message in {"account not found", "story draft not found"} else "validation"
    )
    if message == "story draft not found":
        error_code = "STORY_DRAFT_NOT_FOUND"
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND
        if error_class == "not_found"
        else status.HTTP_400_BAD_REQUEST,
        error_code=error_code,
        error_class=error_class,
        message=message,
    )


__all__ = ["router"]
