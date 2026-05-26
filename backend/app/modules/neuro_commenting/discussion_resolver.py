from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, cast

from app.adapters.tdlib_auth import TdlibClientFactory
from app.config import Settings, settings
from app.models import NeuroCommentTarget
from app.modules.neuro_commenting.errors import NeuroRuntimeUnavailableError
from app.modules.neuro_commenting.tdlib_helpers import checked_tdlib_query, dict_or_empty
from app.modules.neuro_commenting.tdlib_runtime import NeuroTdlibRuntime


DISCUSSION_MESSAGE_NOT_RESOLVED = "DISCUSSION_MESSAGE_NOT_RESOLVED"
TARGET_NO_DISCUSSION = "TARGET_NO_DISCUSSION"
_INT_COERCION_ERRORS = (TypeError, ValueError)


@dataclass(frozen=True)
class DiscussionMessageResolution:
    discussion_chat_id: str | None
    discussion_message_id: str | None
    error_code: str | None = None


class DiscussionMessageResolver(Protocol):
    def resolve(
        self,
        *,
        account_id: str,
        target: NeuroCommentTarget,
        source_chat_id: str,
        source_message_id: str,
    ) -> DiscussionMessageResolution: ...


class FakeDiscussionMessageResolver:
    def __init__(
        self,
        *,
        discussion_chat_id: str | None = None,
        discussion_message_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        self._discussion_chat_id = discussion_chat_id
        self._discussion_message_id = discussion_message_id
        self._error_code = error_code

    def resolve(
        self,
        *,
        account_id: str,
        target: NeuroCommentTarget,
        source_chat_id: str,
        source_message_id: str,
    ) -> DiscussionMessageResolution:
        _ = (account_id, source_chat_id, source_message_id)
        discussion_chat_id = self._discussion_chat_id or target.discussion_chat_id
        if not discussion_chat_id:
            return DiscussionMessageResolution(None, None, TARGET_NO_DISCUSSION)
        if self._error_code is not None or not self._discussion_message_id:
            return DiscussionMessageResolution(
                discussion_chat_id,
                self._discussion_message_id,
                self._error_code or DISCUSSION_MESSAGE_NOT_RESOLVED,
            )
        return DiscussionMessageResolution(
            discussion_chat_id,
            self._discussion_message_id,
            None,
        )


class TdlibDiscussionMessageResolver:
    def __init__(
        self,
        *,
        config: Settings = settings,
        client_factory: TdlibClientFactory | None = None,
        runtime: NeuroTdlibRuntime | None = None,
        history_limit: int = 50,
    ) -> None:
        self._config = config
        self._runtime = runtime or NeuroTdlibRuntime(config=config, client_factory=client_factory)
        self._history_limit = history_limit

    def resolve(
        self,
        *,
        account_id: str,
        target: NeuroCommentTarget,
        source_chat_id: str,
        source_message_id: str,
    ) -> DiscussionMessageResolution:
        if not target.discussion_chat_id:
            return DiscussionMessageResolution(None, None, TARGET_NO_DISCUSSION)
        try:
            discussion_chat_id = _require_int_id(target.discussion_chat_id)
        except NeuroRuntimeUnavailableError:
            return DiscussionMessageResolution(
                target.discussion_chat_id, None, TARGET_NO_DISCUSSION
            )
        with self._runtime.ready_client_context(account_id) as client:
            response = checked_tdlib_query(
                client,
                {
                    "@type": "getChatHistory",
                    "chat_id": discussion_chat_id,
                    "from_message_id": 0,
                    "offset": 0,
                    "limit": self._history_limit,
                    "only_local": False,
                },
                timeout_seconds=self._config.tdlib_receive_timeout_seconds,
            )
        messages = response.get("messages")
        message_list = cast(list[Any], messages) if isinstance(messages, list) else []
        for item in message_list:
            message = dict_or_empty(item)
            if _message_matches_source(
                message,
                source_chat_id=source_chat_id,
                source_message_id=source_message_id,
            ):
                message_id = message.get("id")
                if message_id is not None and str(message_id).strip():
                    return DiscussionMessageResolution(
                        target.discussion_chat_id,
                        str(message_id),
                        None,
                    )
        return DiscussionMessageResolution(
            target.discussion_chat_id,
            None,
            DISCUSSION_MESSAGE_NOT_RESOLVED,
        )


def build_discussion_message_resolver(config: Settings = settings) -> DiscussionMessageResolver:
    if not config.neuro_comment_tdlib_observer_enabled:
        return FakeDiscussionMessageResolver()
    return TdlibDiscussionMessageResolver(config=config)


def _message_matches_source(
    message: dict[str, Any], *, source_chat_id: str, source_message_id: str
) -> bool:
    forward_info = dict_or_empty(message.get("forward_info"))
    source = dict_or_empty(forward_info.get("source"))
    if _ids_match(source, source_chat_id=source_chat_id, source_message_id=source_message_id):
        return True
    origin = dict_or_empty(forward_info.get("origin"))
    if _ids_match(origin, source_chat_id=source_chat_id, source_message_id=source_message_id):
        return True
    reply_to = dict_or_empty(message.get("reply_to"))
    return _ids_match(reply_to, source_chat_id=source_chat_id, source_message_id=source_message_id)


def _ids_match(value: dict[str, Any], *, source_chat_id: str, source_message_id: str) -> bool:
    chat_id = value.get("chat_id") or value.get("origin_chat_id") or value.get("from_chat_id")
    message_id = (
        value.get("message_id") or value.get("origin_message_id") or value.get("source_message_id")
    )
    return str(chat_id or "") == str(source_chat_id) and str(message_id or "") == str(
        source_message_id
    )


def _require_int_id(value: object) -> int:
    try:
        return int(str(value))
    except _INT_COERCION_ERRORS:
        raise NeuroRuntimeUnavailableError("chat not found", error_code="CHAT_NOT_FOUND") from None
