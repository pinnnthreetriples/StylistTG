from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.account_context import account_id_header
from app.db import get_session
from app.errors import AppError
from app.schemas import StoryDraftCreate, StoryDraftRead, StoryDraftUpdate
from app.services.story_drafts import (
    create_story_draft,
    delete_story_draft,
    list_story_drafts,
    update_story_draft,
)

router = APIRouter(prefix="/api/story-drafts", tags=["story-drafts"])


@router.get("/{account_id}", response_model=list[StoryDraftRead])
def get_story_drafts(account_id: str, session: Session = Depends(get_session)):
    return list_story_drafts(session, account_id)


@router.get("", response_model=list[StoryDraftRead])
def get_story_drafts_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    return list_story_drafts(session, account_id)


@router.post("", response_model=StoryDraftRead, status_code=status.HTTP_201_CREATED)
def post_story_draft(payload: StoryDraftCreate, session: Session = Depends(get_session)):
    try:
        return create_story_draft(session, payload.model_dump())
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


@router.patch("/{draft_id}", response_model=StoryDraftRead)
def patch_story_draft(draft_id: str, payload: StoryDraftUpdate, session: Session = Depends(get_session)):
    try:
        return update_story_draft(session, draft_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_story_draft(draft_id: str, session: Session = Depends(get_session)):
    try:
        delete_story_draft(session, draft_id)
    except ValueError as exc:
        raise _story_draft_error(exc) from exc


def _story_draft_error(exc: ValueError) -> AppError:
    message = str(exc)
    error_code = "ACCOUNT_NOT_FOUND" if message == "account not found" else "VALIDATION_ERROR"
    error_class = "not_found" if message in {"account not found", "story draft not found"} else "validation"
    if message == "story draft not found":
        error_code = "STORY_DRAFT_NOT_FOUND"
    return AppError(
        status_code=status.HTTP_404_NOT_FOUND if error_class == "not_found" else status.HTTP_400_BAD_REQUEST,
        error_code=error_code,
        error_class=error_class,
        message=message,
    )
