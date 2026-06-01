from __future__ import annotations

# pyright: reportUnusedFunction=false

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountStoryPost, utc_now

from .sync_types import JsonDict, JsonList


def _sync_story_posts(
    session: Session,
    *,
    account_id: str,
    live_stories: JsonList,
) -> list[AccountStoryPost]:
    live_by_id = {
        str(story["telegram_story_id"]): story
        for story in live_stories
        if story.get("telegram_story_id") is not None
    }
    posts = list(
        session.execute(select(AccountStoryPost).where(AccountStoryPost.account_id == account_id))
        .scalars()
        .all()
    )
    posts_by_story_id = {
        str(post.telegram_story_id): post for post in posts if post.telegram_story_id is not None
    }
    now = utc_now()

    _expire_missing_story_posts(posts, live_by_id, now)
    for story_id, story in live_by_id.items():
        post = _upsert_story_post(
            session,
            account_id=account_id,
            story_id=story_id,
            story=story,
            posts_by_story_id=posts_by_story_id,
        )
        if post not in posts:
            posts.append(post)

    session.commit()
    return [
        post
        for post in posts
        if post.telegram_story_id is not None and str(post.telegram_story_id) in live_by_id
    ]


def _expire_missing_story_posts(
    posts: list[AccountStoryPost], live_by_id: dict[str, JsonDict], now: datetime
) -> None:
    for post in posts:
        if post.telegram_story_id is None:
            continue
        if str(post.telegram_story_id) not in live_by_id and post.status in {"posted", "active"}:
            post.status = "expired"
            post.expires_at = post.expires_at or now


def _upsert_story_post(
    session: Session,
    *,
    account_id: str,
    story_id: str,
    story: JsonDict,
    posts_by_story_id: dict[str, AccountStoryPost],
) -> AccountStoryPost:
    post = posts_by_story_id.get(story_id)
    if post is None:
        post = _new_story_post(account_id=account_id, story_id=story_id, story=story)
        session.add(post)
        posts_by_story_id[story_id] = post
        return post
    _update_story_post(post, story)
    return post


def _new_story_post(*, account_id: str, story_id: str, story: JsonDict) -> AccountStoryPost:
    return AccountStoryPost(
        account_id=account_id,
        job_id=None,
        step_key="live_sync",
        story_poster_chat_id=story.get("story_poster_chat_id"),
        telegram_story_id=story_id,
        temporary_story_id=None,
        media_kind=story["media_kind"],
        asset_id=None,
        caption=story.get("caption"),
        privacy_preset=story.get("privacy_preset") or "unknown",
        active_period_seconds=int(story.get("active_period_seconds") or 86400),
        protect_content=False,
        can_be_deleted=bool(story.get("can_be_deleted")),
        status="active",
        raw_tdlib_json=story.get("raw_tdlib_json"),
        posted_at=story.get("posted_at"),
        expires_at=story.get("expires_at"),
    )


def _update_story_post(post: AccountStoryPost, story: JsonDict) -> None:
    post.status = "active"
    post.story_poster_chat_id = story.get("story_poster_chat_id") or post.story_poster_chat_id
    post.media_kind = story["media_kind"]
    post.caption = story.get("caption")
    post.privacy_preset = story.get("privacy_preset") or post.privacy_preset
    post.raw_tdlib_json = story.get("raw_tdlib_json")
    post.can_be_deleted = bool(story.get("can_be_deleted"))
    post.posted_at = story.get("posted_at") or post.posted_at
    post.expires_at = story.get("expires_at") or post.expires_at
