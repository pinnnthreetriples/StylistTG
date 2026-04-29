from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.account_context import account_id_header
from app.db import get_session
from app.errors import AppError
from app.schemas import StoryCapabilitiesRead
from app.services.story_capabilities import build_story_capabilities

router = APIRouter(prefix="/api/story-capabilities", tags=["story-capabilities"])


@router.get("/{account_id}", response_model=StoryCapabilitiesRead)
def get_story_capabilities(account_id: str, session: Session = Depends(get_session)):
    return _story_capabilities_response(account_id, session)


@router.get("", response_model=StoryCapabilitiesRead)
def get_story_capabilities_from_header(
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
):
    return _story_capabilities_response(account_id, session)


def _story_capabilities_response(account_id: str, session: Session):
    try:
        return build_story_capabilities(session, account_id)
    except ValueError as exc:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message=str(exc),
        ) from exc
