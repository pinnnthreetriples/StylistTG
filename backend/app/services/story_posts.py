from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountStoryPost, utc_now
from app.services.profile_sync import ProfileSyncAdapter


def create_story_post_from_result(
    session: Session,
    *,
    account_id: str,
    job_id: str,
    step_key: str,
    story: dict[str, Any],
) -> AccountStoryPost:
    existing = session.execute(
        select(AccountStoryPost)
        .where(AccountStoryPost.job_id == job_id)
        .where(AccountStoryPost.step_key == step_key)
    ).scalars().first()
    if existing is not None:
        return existing

    now = utc_now()
    active_period = int(story.get("active_period_seconds") or 86400)
    raw_tdlib_json = story.get("raw_tdlib_json") if isinstance(story.get("raw_tdlib_json"), dict) else {}
    post = AccountStoryPost(
        account_id=account_id,
        job_id=job_id,
        step_key=step_key,
        telegram_story_id=story.get("telegram_story_id"),
        temporary_story_id=story.get("temporary_story_id"),
        media_kind=story.get("media_kind") or "image",
        asset_id=story.get("asset_id"),
        caption=story.get("caption"),
        privacy_preset=story.get("privacy_preset") or "contacts",
        active_period_seconds=active_period,
        protect_content=bool(story.get("protect_content")),
        status=story.get("status") or "posted",
        story_poster_chat_id=story.get("story_poster_chat_id"),
        can_be_deleted=_story_can_be_deleted(story, raw_tdlib_json),
        failure_code=story.get("failure_code"),
        failure_message=story.get("failure_message"),
        raw_tdlib_json=raw_tdlib_json or story.get("raw_tdlib_json"),
        posted_at=now if story.get("status", "posted") == "posted" else None,
        expires_at=now + timedelta(seconds=active_period) if story.get("status", "posted") == "posted" else None,
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


def _story_can_be_deleted(story: dict[str, Any], raw_tdlib_json: dict[str, Any]) -> bool:
    return bool(
        story.get("can_be_deleted")
        or raw_tdlib_json.get("can_be_deleted")
        or (
            raw_tdlib_json.get("is_posted_to_chat_page")
            and raw_tdlib_json.get("can_toggle_is_posted_to_chat_page")
        )
    )


def list_story_posts(session: Session, account_id: str, *, limit: int = 10) -> list[AccountStoryPost]:
    statement = (
        select(AccountStoryPost)
        .where(AccountStoryPost.account_id == account_id)
        .where(AccountStoryPost.status.in_(["posted", "active"]))
        .order_by(AccountStoryPost.created_at.desc())
        .limit(limit)
    )
    return list(session.execute(statement).scalars().all())


def delete_profile_story(
    session: Session,
    *,
    account_id: str,
    story_post_id: str,
    adapter: ProfileSyncAdapter,
) -> None:
    post = session.get(AccountStoryPost, story_post_id)
    if post is None or post.account_id != account_id:
        raise ValueError("story post not found")
    if post.status not in {"posted", "active"}:
        raise ValueError("story post is not active")
    if not post.telegram_story_id:
        raise ValueError("story post has no telegram story id")
    raw = post.raw_tdlib_json if isinstance(post.raw_tdlib_json, dict) else {}
    can_remove_from_profile = bool(raw.get("is_posted_to_chat_page") and raw.get("can_toggle_is_posted_to_chat_page"))
    if not post.can_be_deleted and not can_remove_from_profile:
        raise ValueError("story post cannot be deleted")

    if post.can_be_deleted:
        try:
            adapter.delete_story(account_id, post.story_poster_chat_id, post.telegram_story_id)
        except RuntimeError as exc:
            if "not found" not in str(exc).lower():
                raise
    else:
        try:
            adapter.remove_story_from_profile(account_id, post.story_poster_chat_id, post.telegram_story_id)
        except RuntimeError as exc:
            if "not found" not in str(exc).lower():
                raise
    _mark_story_removed(session, post)


def _mark_story_removed(session: Session, post: AccountStoryPost) -> None:
    post.status = "removed"
    post.expires_at = post.expires_at or utc_now()
    session.add(post)
    session.commit()


def story_post_payload(post: AccountStoryPost) -> dict[str, Any]:
    return {
        "id": post.id,
        "story_poster_chat_id": post.story_poster_chat_id,
        "telegram_story_id": post.telegram_story_id,
        "temporary_story_id": post.temporary_story_id,
        "media_kind": post.media_kind,
        "asset_id": post.asset_id,
        "caption": post.caption,
        "privacy_preset": post.privacy_preset,
        "active_period_seconds": post.active_period_seconds,
        "protect_content": post.protect_content,
        "can_be_deleted": post.can_be_deleted,
        "status": post.status,
        "failure_code": post.failure_code,
        "failure_message": post.failure_message,
        "posted_at": post.posted_at,
        "expires_at": post.expires_at,
    }
