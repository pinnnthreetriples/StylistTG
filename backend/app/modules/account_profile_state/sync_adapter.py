from __future__ import annotations

# pyright: reportPrivateUsage=false

from typing import Callable, cast

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibClient,
    ensure_tdlib_ready,
)
from app.config import Settings, settings
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib

from .sync_media import _fetch_profile_audio, _fetch_profile_photo
from .sync_payloads import _extract_text, _extract_username, _send_query_checked
from .sync_story_payloads import _active_story_payload
from .sync_types import JsonDict, JsonList, ProfileSyncAdapter


class UnavailableProfileSyncAdapter:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def fetch_current_profile(self, account_id: str) -> JsonDict:
        raise RuntimeError(self._reason)

    def fetch_active_stories(self, account_id: str) -> JsonList:
        raise RuntimeError(self._reason)

    def fetch_profile_snapshot(self, account_id: str) -> JsonDict:
        raise RuntimeError(self._reason)

    def delete_story(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None:
        raise RuntimeError(self._reason)

    def remove_story_from_profile(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None:
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

    def fetch_current_profile(self, account_id: str) -> JsonDict:
        snapshot = self.fetch_profile_snapshot(account_id)
        return cast(JsonDict, snapshot["profile"])

    def fetch_active_stories(self, account_id: str) -> JsonList:
        snapshot = self.fetch_profile_snapshot(account_id)
        return cast(JsonList, snapshot["stories"])

    def fetch_profile_snapshot(self, account_id: str) -> JsonDict:
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

    def delete_story(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None:
        client = None
        try:
            client = self._client_factory.create(account_id)
            self._wait_until_ready(client, account_id)
            chat_id = _prepare_story_action(client, story_poster_chat_id, story_id, self._config)
            _send_query_checked(
                client,
                {
                    "@type": "deleteStory",
                    "story_poster_chat_id": chat_id,
                    "story_id": int(story_id),
                },
                self._config.tdlib_auth_timeout_seconds,
            )
        finally:
            if client is not None:
                client.close()

    def remove_story_from_profile(
        self, account_id: str, story_poster_chat_id: str | None, story_id: str
    ) -> None:
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
        ensure_tdlib_ready(
            client,
            account_id=account_id,
            config=self._config,
            proxy_applier=self._proxy_applier,
            timeout_message="TDLib profile sync readiness timed out",
        )


def build_profile_sync_adapter(config: Settings = settings) -> ProfileSyncAdapter:
    if not config.tdlib_api_id or not config.tdlib_api_hash:
        return UnavailableProfileSyncAdapter("TDLib credentials are not configured")
    try:
        return TdlibProfileSyncAdapter(
            client_factory=RealTdJsonClientFactory(config.tdlib_shared_library_path),
            config=config,
            proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(
                client, account_id, config=config
            ),
        )
    except OSError as exc:
        return UnavailableProfileSyncAdapter(str(exc))


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
        {
            "@type": "getStory",
            "story_poster_chat_id": chat_id,
            "story_id": int(story_id),
            "only_local": False,
        },
        config.tdlib_auth_timeout_seconds,
    )
    return chat_id


def _fetch_profile_page_stories(
    client: TdlibClient, chat_id: int | None, config: Settings
) -> JsonList:
    if chat_id is None:
        return []
    response = _send_query_checked(
        client,
        {
            "@type": "getChatPostedToChatPageStories",
            "chat_id": chat_id,
            "from_story_id": 0,
            "limit": 20,
        },
        config.tdlib_auth_timeout_seconds,
    )
    response_stories = cast(list[object], response.get("stories") or [])
    return [
        _active_story_payload(cast(JsonDict, story), story_poster_chat_id=chat_id)
        for story in response_stories
        if isinstance(story, dict)
    ]


def _fetch_active_stories(client: TdlibClient, chat_id: int | None, config: Settings) -> JsonList:
    if chat_id is None:
        return []
    active = _send_query_checked(
        client,
        {"@type": "getChatActiveStories", "chat_id": chat_id},
        config.tdlib_auth_timeout_seconds,
    )
    stories: JsonList = []
    active_stories = cast(list[object], active.get("stories") or [])
    for info_value in active_stories:
        if not isinstance(info_value, dict):
            continue
        info = cast(JsonDict, info_value)
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
