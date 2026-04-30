from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import time
from typing import Callable, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibClient,
    _extract_authorization_state,
    _tdlib_parameters_query,
    map_authorization_state,
)
from app.config import Settings, settings
from app.models import AccountProfileState, AccountStoryPost, utc_now
from app.services.accounts import get_account
from app.services.assets import save_profile_audio_asset, save_profile_photo_asset
from app.services.profile_audio_state import clear_profile_audio_state, upsert_profile_audio_state
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib


class ProfileSyncAdapter(Protocol):
    def fetch_profile_snapshot(self, account_id: str) -> dict: ...
    def fetch_current_profile(self, account_id: str) -> dict: ...
    def fetch_active_stories(self, account_id: str) -> list[dict]: ...
    def delete_story(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None: ...
    def remove_story_from_profile(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None: ...


class UnavailableProfileSyncAdapter:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def fetch_current_profile(self, account_id: str) -> dict:
        raise RuntimeError(self._reason)

    def fetch_active_stories(self, account_id: str) -> list[dict]:
        raise RuntimeError(self._reason)

    def fetch_profile_snapshot(self, account_id: str) -> dict:
        raise RuntimeError(self._reason)

    def delete_story(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None:
        raise RuntimeError(self._reason)

    def remove_story_from_profile(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None:
        raise RuntimeError(self._reason)


class TdlibProfileSyncAdapter:
    def __init__(
        self,
        *,
        client_factory: RealTdJsonClientFactory,
        config: Settings = settings,
        proxy_applier: Callable[[TdlibClient, str], bool] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._config = config
        self._proxy_applier = proxy_applier

    def fetch_current_profile(self, account_id: str) -> dict:
        snapshot = self.fetch_profile_snapshot(account_id)
        return snapshot["profile"]

    def fetch_active_stories(self, account_id: str) -> list[dict]:
        snapshot = self.fetch_profile_snapshot(account_id)
        return snapshot["stories"]

    def fetch_profile_snapshot(self, account_id: str) -> dict:
        client = None
        try:
            client = self._client_factory.create(account_id)
            self._wait_until_ready(client, account_id)
            me = _send_query_checked(
                client,
                {"@type": "getMe"},
                self._config.tdlib_receive_timeout_seconds,
            )
            user_id = me.get("id")
            full_info = _send_query_checked(
                client,
                {"@type": "getUserFullInfo", "user_id": user_id},
                self._config.tdlib_receive_timeout_seconds,
            )
            chat_id = _current_user_chat_id(client, user_id, self._config)
            profile_stories = _fetch_profile_page_stories(client, chat_id, self._config)
            active_stories = _fetch_active_stories(client, chat_id, self._config)
            profile_photo = _fetch_profile_photo(client, user_id, full_info, self._config)
            profile_audio = _fetch_profile_audio(client, user_id, full_info, self._config)
            return {
                "profile": {
                    "telegram_user_id": str(user_id) if user_id is not None else None,
                    "first_name": me.get("first_name"),
                    "last_name": me.get("last_name"),
                    "username": _extract_username(me),
                    "bio": _extract_text(full_info.get("bio")),
                },
                "profile_photo": profile_photo,
                "profile_audio": profile_audio,
                "stories": profile_stories or active_stories,
                "diagnostics": {
                    "profile_page_story_count": len(profile_stories),
                    "active_story_count": len(active_stories),
                },
            }
        finally:
            if client is not None:
                client.close()

    def delete_story(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None:
        client = None
        try:
            client = self._client_factory.create(account_id)
            self._wait_until_ready(client, account_id)
            chat_id = _prepare_story_action(client, story_poster_chat_id, story_id, self._config)
            _send_query_checked(
                client,
                {"@type": "deleteStory", "story_poster_chat_id": chat_id, "story_id": int(story_id)},
                self._config.tdlib_auth_timeout_seconds,
            )
        finally:
            if client is not None:
                client.close()

    def remove_story_from_profile(self, account_id: str, story_poster_chat_id: str | None, story_id: str) -> None:
        client = None
        try:
            client = self._client_factory.create(account_id)
            self._wait_until_ready(client, account_id)
            chat_id = _prepare_story_action(client, story_poster_chat_id, story_id, self._config)
            _send_query_checked(
                client,
                {
                    "@type": "toggleStoryIsPostedToChatPage",
                    "story_poster_chat_id": chat_id,
                    "story_id": int(story_id),
                    "is_posted_to_chat_page": False,
                },
                self._config.tdlib_auth_timeout_seconds,
            )
        finally:
            if client is not None:
                client.close()

    def _wait_until_ready(self, client: TdlibClient, account_id: str) -> None:
        proxy_applied = False
        deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
        while time.monotonic() < deadline:
            event = client.receive(self._config.tdlib_receive_timeout_seconds)
            state = _extract_authorization_state(event)
            if state is None:
                continue
            mapped = map_authorization_state(state)
            if mapped.status.value == "wait_tdlib_parameters":
                client.send(_tdlib_parameters_query(self._config, account_id))
                if self._proxy_applier is not None and not proxy_applied:
                    self._proxy_applier(client, account_id)
                    proxy_applied = True
                continue
            if mapped.status.value == "ready":
                return
            raise RuntimeError(mapped.error or mapped.runtime_health)
        raise TimeoutError("TDLib profile sync readiness timed out")


def build_profile_sync_adapter(config: Settings = settings) -> ProfileSyncAdapter:
    if not config.tdlib_api_id or not config.tdlib_api_hash:
        return UnavailableProfileSyncAdapter("TDLib credentials are not configured")
    try:
        return TdlibProfileSyncAdapter(
            client_factory=RealTdJsonClientFactory(config.tdlib_shared_library_path),
            config=config,
            proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(client, account_id, config=config),
        )
    except OSError as exc:
        return UnavailableProfileSyncAdapter(str(exc))


def sync_account_profile_state(
    session: Session,
    account_id: str,
    *,
    adapter: ProfileSyncAdapter,
) -> AccountProfileState:
    account = get_account(session, account_id)
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
) -> dict:
    snapshot = adapter.fetch_profile_snapshot(account_id)
    profile_state = _upsert_profile_state(
        session,
        account_id,
        snapshot.get("profile") or {},
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
    stories = _sync_story_posts(session, account_id=account_id, live_stories=snapshot.get("stories") or [])
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
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")

    live_stories = adapter.fetch_active_stories(account_id)
    return _sync_story_posts(session, account_id=account_id, live_stories=live_stories)


def _upsert_profile_state(
    session: Session,
    account_id: str,
    payload: dict,
    *,
    profile_photo_asset_id: str | None,
) -> AccountProfileState:
    account = get_account(session, account_id)
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


def _sync_story_posts(
    session: Session,
    *,
    account_id: str,
    live_stories: list[dict],
) -> list[AccountStoryPost]:
    live_by_id = {
        str(story["telegram_story_id"]): story
        for story in live_stories
        if story.get("telegram_story_id") is not None
    }
    posts = list(
        session.execute(
            select(AccountStoryPost).where(AccountStoryPost.account_id == account_id)
        ).scalars().all()
    )
    posts_by_story_id = {
        str(post.telegram_story_id): post
        for post in posts
        if post.telegram_story_id is not None
    }
    now = utc_now()

    for post in posts:
        if post.telegram_story_id is None:
            continue
        if str(post.telegram_story_id) not in live_by_id and post.status in {"posted", "active"}:
            post.status = "expired"
            post.expires_at = post.expires_at or now

    for story_id, story in live_by_id.items():
        post = posts_by_story_id.get(story_id)
        if post is None:
            post = AccountStoryPost(
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
            session.add(post)
            posts.append(post)
            continue
        post.status = "active"
        post.story_poster_chat_id = story.get("story_poster_chat_id") or post.story_poster_chat_id
        post.media_kind = story["media_kind"]
        post.caption = story.get("caption")
        post.privacy_preset = story.get("privacy_preset") or post.privacy_preset
        post.raw_tdlib_json = story.get("raw_tdlib_json")
        post.can_be_deleted = bool(story.get("can_be_deleted"))
        post.posted_at = story.get("posted_at") or post.posted_at
        post.expires_at = story.get("expires_at") or post.expires_at

    session.commit()
    return [
        post
        for post in posts
        if post.telegram_story_id is not None and str(post.telegram_story_id) in live_by_id
    ]


def _current_user_chat_id(client: TdlibClient, user_id: object, config: Settings) -> int | None:
    if user_id is None:
        return None
    chat = _send_query_checked(
        client,
        {"@type": "createPrivateChat", "user_id": user_id, "force": True},
        config.tdlib_auth_timeout_seconds,
    )
    chat_id = chat.get("id")
    return int(chat_id) if isinstance(chat_id, int) else None


def _prepare_story_action(
    client: TdlibClient,
    story_poster_chat_id: str | None,
    story_id: str,
    config: Settings,
) -> int:
    me = _send_query_checked(client, {"@type": "getMe"}, config.tdlib_receive_timeout_seconds)
    current_chat_id = _current_user_chat_id(client, me.get("id"), config)
    chat_id = int(story_poster_chat_id) if story_poster_chat_id else current_chat_id
    if chat_id is None:
        raise RuntimeError("TDLib current user chat is unavailable")
    _send_query_checked(
        client,
        {"@type": "getStory", "story_poster_chat_id": chat_id, "story_id": int(story_id), "only_local": False},
        config.tdlib_auth_timeout_seconds,
    )
    return chat_id


def _fetch_profile_page_stories(client: TdlibClient, chat_id: int | None, config: Settings) -> list[dict]:
    if chat_id is None:
        return []
    response = _send_query_checked(
        client,
        {"@type": "getChatPostedToChatPageStories", "chat_id": chat_id, "from_story_id": 0, "limit": 20},
        config.tdlib_auth_timeout_seconds,
    )
    return [_active_story_payload(story, story_poster_chat_id=chat_id) for story in response.get("stories") or []]


def _fetch_active_stories(client: TdlibClient, chat_id: int | None, config: Settings) -> list[dict]:
    if chat_id is None:
        return []
    active = _send_query_checked(
        client,
        {"@type": "getChatActiveStories", "chat_id": chat_id},
        config.tdlib_auth_timeout_seconds,
    )
    stories: list[dict] = []
    for info in active.get("stories") or []:
        story_id = info.get("story_id")
        if story_id is None:
            continue
        story = _send_query_checked(
            client,
            {
                "@type": "getStory",
                "story_poster_chat_id": chat_id,
                "story_id": int(story_id),
                "only_local": False,
            },
            config.tdlib_auth_timeout_seconds,
        )
        stories.append(_active_story_payload(story, story_poster_chat_id=chat_id))
    return stories


def _fetch_profile_photo(client: TdlibClient, user_id: object, full_info: dict, config: Settings) -> dict | None:
    photos = _send_query_checked(
        client,
        {"@type": "getUserProfilePhotos", "user_id": user_id, "offset": 0, "limit": 1},
        config.tdlib_auth_timeout_seconds,
    )
    source = (photos.get("photos") or [None])[0] or full_info.get("photo")
    file = _largest_file(source)
    content = _download_file_bytes(client, file, config)
    if content is None:
        return None
    return {"content": content, "filename": "telegram-profile-photo.jpg", "raw_tdlib_json": source}


def _fetch_profile_audio(client: TdlibClient, user_id: object, full_info: dict, config: Settings) -> dict | None:
    audios = _send_query_checked(
        client,
        {"@type": "getUserProfileAudios", "user_id": user_id, "offset": 0, "limit": 1},
        config.tdlib_auth_timeout_seconds,
    )
    audio = (audios.get("audios") or [None])[0] or full_info.get("first_profile_audio")
    if not isinstance(audio, dict):
        return None
    file = audio.get("audio") if isinstance(audio.get("audio"), dict) else _largest_file(audio)
    content = _download_file_bytes(client, file, config)
    return {
        "telegram_audio_id": str(audio.get("id")) if audio.get("id") is not None else None,
        "telegram_file_id": str(file.get("id")) if isinstance(file, dict) and file.get("id") is not None else None,
        "title": audio.get("title") or None,
        "performer": audio.get("performer") or None,
        "duration_seconds": audio.get("duration"),
        "mime": audio.get("mime_type") or "audio/mpeg",
        "filename": _audio_filename(audio),
        "content": content,
        "raw_tdlib_json": audio,
    }


def _download_file_bytes(client: TdlibClient, file: object, config: Settings) -> bytes | None:
    if not isinstance(file, dict) or not isinstance(file.get("id"), int):
        return None
    downloaded = _send_query_checked(
        client,
        {
            "@type": "downloadFile",
            "file_id": file["id"],
            "priority": 16,
            "offset": 0,
            "limit": 0,
            "synchronous": True,
        },
        config.tdlib_auth_timeout_seconds,
    )
    local = downloaded.get("local") if isinstance(downloaded.get("local"), dict) else {}
    path = local.get("path")
    if not isinstance(path, str) or not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.read_bytes()


def _largest_file(value: object) -> dict | None:
    files: list[dict] = []
    _collect_files(value, files)
    if not files:
        return None
    return max(files, key=lambda item: int(item.get("expected_size") or item.get("size") or 0))


def _collect_files(value: object, files: list[dict]) -> None:
    if isinstance(value, dict):
        if value.get("@type") == "file" and isinstance(value.get("id"), int):
            files.append(value)
        for nested in value.values():
            _collect_files(nested, files)
    elif isinstance(value, list):
        for nested in value:
            _collect_files(nested, files)


def _audio_filename(audio: dict) -> str:
    file_name = audio.get("file_name")
    if isinstance(file_name, str) and file_name:
        return file_name
    title = audio.get("title")
    if isinstance(title, str) and title:
        return f"{title}.mp3"
    return "telegram-profile-audio.mp3"


def _save_synced_profile_photo(
    session: Session,
    *,
    account_id: str,
    photo: object,
    config: Settings,
) -> str | None:
    if not isinstance(photo, dict) or not isinstance(photo.get("content"), bytes):
        return None
    asset = save_profile_photo_asset(
        session,
        filename=str(photo.get("filename") or "telegram-profile-photo.jpg"),
        content=photo["content"],
        storage_root=config.storage_root,
    )
    return asset.id


def _sync_profile_audio_state(
    session: Session,
    *,
    account_id: str,
    audio: object,
    config: Settings,
) -> None:
    if not isinstance(audio, dict):
        clear_profile_audio_state(session, account_id=account_id)
        return

    source_asset_id = None
    if isinstance(audio.get("content"), bytes):
        try:
            asset = save_profile_audio_asset(
                session,
                filename=str(audio.get("filename") or "telegram-profile-audio.mp3"),
                content=audio["content"],
                storage_root=config.storage_root,
                max_bytes=config.profile_audio_max_bytes,
            )
            source_asset_id = asset.id
        except ValueError:
            source_asset_id = None

    upsert_profile_audio_state(
        session,
        account_id=account_id,
        telegram_file_id=audio.get("telegram_file_id"),
        source_asset_id=source_asset_id,
        title=audio.get("title"),
        performer=audio.get("performer"),
        duration_seconds=audio.get("duration_seconds"),
        mime=audio.get("mime"),
        telegram_audio_id=audio.get("telegram_audio_id"),
        raw_tdlib_json=audio.get("raw_tdlib_json"),
    )


def _extract_username(me: dict) -> str | None:
    usernames = me.get("usernames") or {}
    editable = usernames.get("editable_username")
    if editable:
        return editable
    active = usernames.get("active_usernames") or []
    return active[0] if active else None


def _extract_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get("text")
        return text if isinstance(text, str) else None
    return None


def _send_query_checked(client: TdlibClient, query: dict, timeout_seconds: float) -> dict:
    response = client.send_query(query, timeout_seconds)
    if response.get("@type") == "error":
        message = response.get("message") or "TDLib query failed"
        raise RuntimeError(str(message))
    return response


def _active_story_payload(story: dict, *, story_poster_chat_id: int | None = None) -> dict:
    story_id = story.get("id")
    poster_chat_id = story.get("story_poster_chat_id") or story.get("poster_chat_id") or story_poster_chat_id
    posted_at = _datetime_from_unix(story.get("date"))
    active_period = 86400
    return {
        "story_poster_chat_id": str(poster_chat_id) if poster_chat_id is not None else None,
        "telegram_story_id": str(story_id) if story_id is not None else None,
        "media_kind": _story_media_kind(story),
        "caption": _extract_text(story.get("caption")),
        "privacy_preset": _story_privacy_preset(story.get("privacy_settings")),
        "active_period_seconds": active_period,
        "can_be_deleted": bool(story.get("can_be_deleted") or story.get("can_toggle_is_posted_to_chat_page")),
        "posted_at": posted_at,
        "expires_at": posted_at + timedelta(seconds=active_period) if posted_at else None,
        "raw_tdlib_json": story,
    }


def _story_media_kind(story: dict) -> str:
    content = story.get("content") if isinstance(story.get("content"), dict) else {}
    content_type = content.get("@type")
    return "video" if content_type == "storyContentVideo" else "image"


def _story_privacy_preset(privacy: object) -> str:
    if not isinstance(privacy, dict):
        return "unknown"
    return {
        "storyPrivacySettingsEveryone": "public",
        "storyPrivacySettingsContacts": "contacts",
        "storyPrivacySettingsCloseFriends": "close_friends",
        "storyPrivacySettingsSelectedUsers": "selected_users",
    }.get(str(privacy.get("@type")), "unknown")


def _datetime_from_unix(value: object) -> datetime | None:
    if not isinstance(value, int):
        return None
    return datetime.fromtimestamp(value, UTC)
