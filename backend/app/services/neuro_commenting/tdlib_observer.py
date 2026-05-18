from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from app.adapters.tdlib_auth import TdlibClient, TdlibClientFactory
from app.config import Settings, settings
from app.models import NeuroCommentTarget
from app.services.neuro_commenting.errors import NeuroRuntimeUnavailableError
from app.services.neuro_commenting.tdlib_runtime import NeuroTdlibRuntime
from app.services.tdlib_client import safe_tdlib_error_message


@dataclass(frozen=True)
class ObservedTelegramPost:
    source_chat_id: str
    source_message_id: str
    post_text: str | None
    media_summary: str | None
    language: str | None


@dataclass(frozen=True)
class TargetMetadata:
    channel_id: str | None
    discussion_chat_id: str | None
    title: str | None
    username: str | None
    status: str


class TelegramPostObserver(Protocol):
    def refresh_target_metadata(
        self, account_id: str, target: NeuroCommentTarget
    ) -> TargetMetadata: ...

    def fetch_recent_posts(
        self, account_id: str, target: NeuroCommentTarget, limit: int
    ) -> list[ObservedTelegramPost]: ...


class FakeTelegramPostObserver:
    def __init__(
        self,
        *,
        metadata: TargetMetadata | None = None,
        posts: list[ObservedTelegramPost] | None = None,
    ) -> None:
        self._metadata = metadata
        self._posts = list(posts or [])

    def refresh_target_metadata(
        self, account_id: str, target: NeuroCommentTarget
    ) -> TargetMetadata:
        _ = account_id
        return self._metadata or TargetMetadata(
            channel_id=target.channel_id or target.channel_ref,
            discussion_chat_id=target.discussion_chat_id,
            title=target.title,
            username=target.username,
            status=target.status,
        )

    def fetch_recent_posts(
        self, account_id: str, target: NeuroCommentTarget, limit: int
    ) -> list[ObservedTelegramPost]:
        _ = (account_id, target)
        return self._posts[:limit]


class TdlibTelegramPostObserver:
    def __init__(
        self,
        *,
        config: Settings = settings,
        client_factory: TdlibClientFactory | None = None,
        runtime: NeuroTdlibRuntime | None = None,
    ) -> None:
        self._config = config
        self._runtime = runtime or NeuroTdlibRuntime(config=config, client_factory=client_factory)

    def refresh_target_metadata(
        self, account_id: str, target: NeuroCommentTarget
    ) -> TargetMetadata:
        client = self._ready_client(account_id)
        response = _resolve_target_chat(client, target, self._config)
        chat_type = _dict_or_empty(response.get("type"))
        discussion_chat_id = response.get("linked_chat_id") or chat_type.get("linked_chat_id")
        status = "active" if discussion_chat_id else "no_discussion"
        return TargetMetadata(
            channel_id=str(response.get("id") or target.channel_id or target.channel_ref),
            discussion_chat_id=str(discussion_chat_id) if discussion_chat_id else None,
            title=str(response.get("title") or "") or target.title,
            username=target.username,
            status=status,
        )

    def fetch_recent_posts(
        self, account_id: str, target: NeuroCommentTarget, limit: int
    ) -> list[ObservedTelegramPost]:
        client = self._ready_client(account_id)
        chat = _resolve_target_chat(client, target, self._config)
        chat_id = _require_int_id(chat.get("id") or target.channel_id or target.channel_ref)
        response = _checked_query(
            client,
            {
                "@type": "getChatHistory",
                "chat_id": chat_id,
                "from_message_id": 0,
                "offset": 0,
                "limit": limit,
                "only_local": False,
            },
            self._config,
        )
        messages = response.get("messages")
        message_list = cast(list[Any], messages) if isinstance(messages, list) else []
        posts: list[ObservedTelegramPost] = []
        for message_item in message_list:
            message = _dict_or_empty(message_item)
            if not message:
                continue
            content = _dict_or_empty(message.get("content"))
            text_obj = _dict_or_empty(content.get("text"))
            text_value = text_obj.get("text")
            text = text_value if isinstance(text_value, str) else None
            content_type = content.get("@type")
            chat_value = message.get("chat_id")
            message_value = message.get("id")
            if message_value is None or str(message_value).strip() == "":
                continue
            posts.append(
                ObservedTelegramPost(
                    source_chat_id=str(chat_value or chat_id),
                    source_message_id=str(message_value or ""),
                    post_text=text,
                    media_summary=str(content_type) if content_type else None,
                    language=None,
                )
            )
        return posts

    def _ready_client(self, account_id: str) -> TdlibClient:
        return self._runtime.ready_client(account_id)


def _dict_or_empty(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return cast(dict[str, Any], value)


def _resolve_target_chat(
    client: TdlibClient, target: NeuroCommentTarget, config: Settings
) -> dict[str, Any]:
    if target.channel_id:
        return _checked_query(
            client, {"@type": "getChat", "chat_id": _require_int_id(target.channel_id)}, config
        )
    username = target.channel_ref.lstrip("@").strip()
    if username:
        return _checked_query(client, {"@type": "searchPublicChat", "username": username}, config)
    raise NeuroRuntimeUnavailableError(
        "target channel is not resolvable", error_code="CHAT_NOT_FOUND"
    )


def _require_int_id(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        raise NeuroRuntimeUnavailableError("chat not found", error_code="CHAT_NOT_FOUND") from None


def build_telegram_post_observer(config: Settings = settings) -> TelegramPostObserver:
    if not config.neuro_comment_tdlib_observer_enabled:
        return FakeTelegramPostObserver()
    return TdlibTelegramPostObserver(config=config)


def _checked_query(
    client: TdlibClient, payload: dict[str, Any], config: Settings
) -> dict[str, Any]:
    try:
        response = client.send_query(payload, config.tdlib_receive_timeout_seconds)
    except Exception as exc:
        raise NeuroRuntimeUnavailableError(
            safe_tdlib_error_message(exc), error_code="TDLIB_RUNTIME_UNAVAILABLE"
        ) from exc
    if response.get("@type") == "error":
        raise NeuroRuntimeUnavailableError(
            safe_tdlib_error_message(response), error_code="TDLIB_RUNTIME_UNAVAILABLE"
        )
    return response
