from __future__ import annotations

# pyright: reportPrivateUsage=false

import hashlib
from typing import cast

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import Account, AccountProfileState, AccountStoryPost, utc_now

from .sync_adapter import (
    TdlibProfileSyncAdapter,
    UnavailableProfileSyncAdapter,
    build_profile_sync_adapter,
)
from .sync_media import _save_synced_profile_photo, _sync_profile_audio_state
from .sync_payloads import _extract_text
from .sync_stories import _sync_story_posts
from .sync_types import JsonDict, JsonList, ProfileSyncAdapter


def sync_account_profile_state(
    session: Session,
    account_id: str,
    *,
    adapter: ProfileSyncAdapter,
) -> AccountProfileState:
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError("account not found")

    payload = adapter.fetch_current_profile(account_id)
    profile_state = account.profile_state
    if profile_state is None:
        profile_state = AccountProfileState(account_id=account.id)
        account.profile_state = profile_state

    profile_state.telegram_user_id = payload.get("telegram_user_id")
    profile_state.first_name = payload.get("first_name")
    profile_state.last_name = payload.get("last_name")
    profile_state.username = payload.get("username")
    profile_state.bio = _extract_text(payload.get("bio"))
    profile_state.bio_hash = _compute_bio_hash(profile_state.bio)
    profile_state.synced_at = utc_now()

    if payload.get("telegram_user_id"):
        account.telegram_user_id = payload["telegram_user_id"]

    session.add(profile_state)
    session.commit()
    session.refresh(account)
    session.refresh(profile_state)
    return profile_state


def sync_account_profile_snapshot(
    session: Session,
    account_id: str,
    *,
    adapter: ProfileSyncAdapter,
    config: Settings = settings,
) -> JsonDict:
    snapshot = adapter.fetch_profile_snapshot(account_id)
    profile_payload = cast(JsonDict, snapshot.get("profile") or {})
    live_stories = cast(JsonList, snapshot.get("stories") or [])
    profile_state = _upsert_profile_state(
        session,
        account_id,
        profile_payload,
        profile_photo_asset_id=_save_synced_profile_photo(
            session,
            account_id=account_id,
            photo=snapshot.get("profile_photo"),
            config=config,
        ),
    )
    _sync_profile_audio_state(
        session,
        account_id=account_id,
        audio=snapshot.get("profile_audio"),
        config=config,
    )
    stories = _sync_story_posts(session, account_id=account_id, live_stories=live_stories)
    return {
        "profile_state": profile_state,
        "story_posts": stories,
        "diagnostics": snapshot.get("diagnostics") or {},
    }


def sync_account_live_story_posts(
    session: Session,
    account_id: str,
    *,
    adapter: ProfileSyncAdapter,
) -> list[AccountStoryPost]:
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError("account not found")

    live_stories = adapter.fetch_active_stories(account_id)
    return _sync_story_posts(session, account_id=account_id, live_stories=live_stories)


def _upsert_profile_state(
    session: Session,
    account_id: str,
    payload: JsonDict,
    *,
    profile_photo_asset_id: str | None,
) -> AccountProfileState:
    account = session.get(Account, account_id)
    if account is None:
        raise ValueError("account not found")

    profile_state = account.profile_state
    if profile_state is None:
        profile_state = AccountProfileState(account_id=account.id)
        account.profile_state = profile_state

    profile_state.telegram_user_id = payload.get("telegram_user_id")
    profile_state.first_name = payload.get("first_name")
    profile_state.last_name = payload.get("last_name")
    profile_state.username = payload.get("username")
    profile_state.bio = _extract_text(payload.get("bio"))
    profile_state.bio_hash = _compute_bio_hash(profile_state.bio)
    if profile_photo_asset_id is not None:
        profile_state.profile_photo_asset_id = profile_photo_asset_id
    profile_state.synced_at = utc_now()

    if payload.get("telegram_user_id"):
        account.telegram_user_id = payload["telegram_user_id"]

    session.add(profile_state)
    session.commit()
    session.refresh(account)
    session.refresh(profile_state)
    return profile_state


def _compute_bio_hash(bio: str | None) -> str | None:
    normalized = " ".join((bio or "").casefold().strip().split())
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


__all__ = [
    "JsonDict",
    "JsonList",
    "ProfileSyncAdapter",
    "TdlibProfileSyncAdapter",
    "UnavailableProfileSyncAdapter",
    "build_profile_sync_adapter",
    "sync_account_live_story_posts",
    "sync_account_profile_snapshot",
    "sync_account_profile_state",
]
