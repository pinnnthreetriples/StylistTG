from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.errors import AppError
from app.modules.account_core.context import account_id_header as _account_id_header
from app.modules.account_profile_state.interfaces import build_profile_sync_adapter
from app.modules.auth.context import AuthContext
from app.modules.auth.dependencies import require_mutation_permission
from app.modules.story.posts import delete_profile_story

router = APIRouter(prefix="/api/story-posts", tags=["story-posts"])


def account_id_header(x_account_id: str = Header(alias="X-Account-Id")) -> str:
    return _account_id_header(x_account_id)


@router.delete("/{story_post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story_post(
    story_post_id: str,
    account_id: str = Depends(account_id_header),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_mutation_permission),
) -> None:
    try:
        delete_profile_story(
            session,
            account_id=account_id,
            story_post_id=story_post_id,
            adapter=build_profile_sync_adapter(),
            workspace_id=auth.workspace_id,
        )
    except ValueError as exc:
        raise _story_post_error(exc) from exc
    except Exception as exc:
        session.rollback()
        raise AppError(
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="STORY_DELETE_FAILED",
            error_class="telegram_sync",
            message="Telegram did not delete the story",
            details={"reason": exc.__class__.__name__, "message": str(exc)},
        ) from exc


def _story_post_error(exc: ValueError) -> AppError:
    message = str(exc)
    if message == "story post not found":
        return AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="STORY_POST_NOT_FOUND",
            error_class="not_found",
            message=message,
        )
    return AppError(
        status_code=status.HTTP_400_BAD_REQUEST,
        error_code="STORY_POST_CANNOT_DELETE",
        error_class="validation",
        message=message,
    )


__all__ = ["router"]
