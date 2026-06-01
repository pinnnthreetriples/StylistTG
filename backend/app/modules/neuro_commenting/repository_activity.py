from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
)
from app.modules.neuro_commenting.errors import not_found


def list_observed_posts(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: str | None = None,
    target_id: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentObservedPost], int]:
    query = (
        session.query(NeuroCommentObservedPost)
        .join(NeuroCommentCampaign)
        .filter(NeuroCommentCampaign.workspace_id == workspace_id)
    )
    if campaign_id is not None:
        query = query.filter(NeuroCommentObservedPost.campaign_id == campaign_id)
    if target_id is not None:
        query = query.filter(NeuroCommentObservedPost.target_id == target_id)
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentObservedPost.seen_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_observed_post_for_workspace(
    session: Session,
    *,
    observed_post_id: str,
    workspace_id: str,
) -> NeuroCommentObservedPost | None:
    return (
        session.query(NeuroCommentObservedPost)
        .join(NeuroCommentCampaign)
        .filter(
            NeuroCommentObservedPost.id == observed_post_id,
            NeuroCommentCampaign.workspace_id == workspace_id,
        )
        .one_or_none()
    )


def require_observed_post_for_workspace(
    session: Session,
    *,
    observed_post_id: str,
    workspace_id: str,
) -> NeuroCommentObservedPost:
    observed_post = get_observed_post_for_workspace(
        session, observed_post_id=observed_post_id, workspace_id=workspace_id
    )
    if observed_post is None:
        raise not_found("observed post not found", "OBSERVED_POST_NOT_FOUND")
    return observed_post


def get_observed_post(
    session: Session,
    *,
    observed_post_id: str,
    campaign_id: str,
) -> NeuroCommentObservedPost | None:
    return (
        session.query(NeuroCommentObservedPost)
        .filter(
            NeuroCommentObservedPost.id == observed_post_id,
            NeuroCommentObservedPost.campaign_id == campaign_id,
        )
        .one_or_none()
    )


def get_observed_post_by_message(
    session: Session,
    *,
    target_id: str,
    source_chat_id: str,
    source_message_id: str,
) -> NeuroCommentObservedPost | None:
    return (
        session.query(NeuroCommentObservedPost)
        .filter(
            NeuroCommentObservedPost.target_id == target_id,
            NeuroCommentObservedPost.source_chat_id == source_chat_id,
            NeuroCommentObservedPost.source_message_id == source_message_id,
        )
        .one_or_none()
    )


def create_or_get_observed_post(
    session: Session,
    *,
    campaign_id: str,
    target_id: str,
    source_chat_id: str,
    source_message_id: str,
    post_text: str | None,
    media_summary: str | None,
    language: str | None,
    matched_mode: str | None,
    matched_keywords: list[str],
    status: str = "seen",
) -> tuple[NeuroCommentObservedPost, bool]:
    existing = get_observed_post_by_message(
        session,
        target_id=target_id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
    )
    if existing is not None:
        return existing, False
    from app.models import new_id

    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign_id,
        target_id=target_id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        post_text=post_text,
        media_summary=media_summary,
        language=language,
        matched_mode=matched_mode,
        matched_keywords=matched_keywords,
        status=status,
    )
    try:
        with session.begin_nested():
            session.add(observed)
            session.flush()
    except IntegrityError:
        existing = get_observed_post_by_message(
            session,
            target_id=target_id,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
        )
        if existing is not None:
            return existing, False
        raise
    return observed, True


def list_attempts(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: str | None = None,
    generated_comment_id: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentAttempt], int]:
    query = (
        session.query(NeuroCommentAttempt)
        .join(NeuroCommentCampaign)
        .filter(NeuroCommentCampaign.workspace_id == workspace_id)
    )
    if campaign_id is not None:
        query = query.filter(NeuroCommentAttempt.campaign_id == campaign_id)
    if generated_comment_id is not None:
        query = query.filter(NeuroCommentAttempt.generated_comment_id == generated_comment_id)
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentAttempt.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_attempt_for_workspace(
    session: Session,
    *,
    attempt_id: str,
    workspace_id: str,
) -> NeuroCommentAttempt | None:
    return (
        session.query(NeuroCommentAttempt)
        .join(NeuroCommentCampaign)
        .filter(
            NeuroCommentAttempt.id == attempt_id,
            NeuroCommentCampaign.workspace_id == workspace_id,
        )
        .one_or_none()
    )


def require_attempt_for_workspace(
    session: Session,
    *,
    attempt_id: str,
    workspace_id: str,
) -> NeuroCommentAttempt:
    attempt = get_attempt_for_workspace(session, attempt_id=attempt_id, workspace_id=workspace_id)
    if attempt is None:
        raise not_found("attempt not found", "ATTEMPT_NOT_FOUND")
    return attempt


def get_attempt_for_generated_comment(
    session: Session,
    *,
    generated_comment_id: str,
) -> NeuroCommentAttempt | None:
    return (
        session.query(NeuroCommentAttempt)
        .filter(NeuroCommentAttempt.generated_comment_id == generated_comment_id)
        .order_by(NeuroCommentAttempt.created_at.asc())
        .first()
    )


def create_attempt_for_generated_comment(
    session: Session, *, comment: NeuroCommentGeneratedComment
) -> NeuroCommentAttempt:
    from app.models import new_id

    attempt = NeuroCommentAttempt(
        id=new_id(),
        campaign_id=comment.campaign_id,
        generated_comment_id=comment.id,
        account_id=comment.account_id,
        target_id=comment.target_id,
        observed_post_id=comment.observed_post_id,
    )
    session.add(attempt)
    session.flush()
    return attempt


def list_events(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentEvent], int]:
    query = session.query(NeuroCommentEvent).filter(NeuroCommentEvent.workspace_id == workspace_id)
    if campaign_id is not None:
        query = query.filter(NeuroCommentEvent.campaign_id == campaign_id)
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentEvent.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def normalize_keywords(value: Sequence[str] | None) -> list[str]:
    if value is None:
        return []
    return [item.strip().lower() for item in value if item.strip()]


def safe_event_data(data: dict[str, Any] | None) -> dict[str, Any]:
    return data or {}
