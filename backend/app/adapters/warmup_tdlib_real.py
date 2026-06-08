from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

import logging
import random
import time
from collections.abc import Callable
from typing import Any, cast

from app.adapters.tdlib_auth import (
    TdlibAuthStatus,
    TdlibClient,
    TdlibClientFactory,
    UnavailableTdlibClientFactory,
    extract_authorization_state,
    map_authorization_state,
    tdlib_parameters_query,
)
from app.adapters.warmup_tdlib_contracts import WarmupActionResult, collect_supported_actions
from app.adapters.warmup_tdlib_errors import _AdapterClientError, _classify_tdlib_error
from app.config import Settings, settings
from app.modules.warmup.typing import compute_typing_duration
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib


_logger = logging.getLogger(__name__)
_INT_COERCION_ERRORS = (TypeError, ValueError)


class RealWarmupTdlibAdapter:
    provider_name = "tdlib_passive"

    def __init__(
        self,
        *,
        client_factory: TdlibClientFactory,
        config: Settings = settings,
        supported_modes: tuple[str, ...] = ("passive", "network", "advanced"),
    ) -> None:
        self._client_factory = client_factory
        self._config = config
        self._supported_actions: set[str] = collect_supported_actions(supported_modes)
        self._clients: dict[str, TdlibClient] = {}

    def is_available(self) -> bool:
        if not self._config.tdlib_api_id or not self._config.tdlib_api_hash:
            return False
        return not isinstance(self._client_factory, UnavailableTdlibClientFactory)

    def supports_action(self, action_type: str) -> bool:
        return action_type in self._supported_actions

    def close(self) -> None:
        for account_id, client in list(self._clients.items()):
            try:
                client.close()
            except Exception:
                _logger.warning(
                    "warmup_tdlib_close_failed",
                    extra={"account_id": account_id},
                    exc_info=True,
                )
            self._clients.pop(account_id, None)

    def execute_action(
        self, *, account_id: str, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        if not self.is_available():
            return WarmupActionResult(
                status="unavailable",
                action_type=action_type,
                error_code="tdlib_passive_not_configured",
                error_class="configuration",
            )
        if not self.supports_action(action_type):
            return WarmupActionResult(
                status="unsupported",
                action_type=action_type,
                error_code="action_not_supported_in_passive",
                error_class="contract",
            )
        try:
            client = self._ensure_ready_client(account_id)
        except _AdapterClientError as exc:
            return exc.as_action_result(action_type)
        handlers: dict[str, Callable[[], WarmupActionResult]] = {
            "get_me": lambda: self._action_get_me(client, action_type),
            "ping_proxy": lambda: self._action_ping_proxy(action_type, context),
            "feed_read": lambda: self._action_feed_read(client, action_type),
            "view_dialogs": lambda: self._action_view_dialogs(client, action_type, context),
            "mark_as_read": lambda: self._action_mark_as_read(client, action_type, context),
            "search_messages": lambda: self._action_search_messages(client, action_type, context),
            "join_chat": lambda: self._action_join_chat(client, action_type, context),
            "channel_browse": lambda: self._action_channel_browse(client, action_type, context),
            "scroll_channels": lambda: self._action_scroll_channels(client, action_type, context),
            "vote_poll": lambda: self._action_vote_poll(client, action_type, context),
            "watch_video": lambda: self._action_watch_video(client, action_type, context),
            "listen_voice": lambda: self._action_listen_voice(client, action_type, context),
            "search_gif": lambda: self._action_search_gif(client, action_type, context),
            "view_stickers": lambda: self._action_view_stickers(client, action_type),
            "inline_bot": lambda: self._action_inline_bot(client, action_type, context),
            "link_preview": lambda: self._action_link_preview(client, action_type, context),
            "forward_message": lambda: self._action_forward_message(client, action_type, context),
            "saved_messages": lambda: self._action_saved_messages(client, action_type, context),
            "sync_contacts": lambda: self._action_sync_contacts(client, action_type, context),
            "archive_chat": lambda: self._action_archive_chat(client, action_type, context),
            "mute_chat": lambda: self._action_mute_chat(client, action_type, context),
            "simulate_typing": lambda: self._action_profile_settings(client, action_type, context),
            "view_profile": lambda: self._action_profile_settings(client, action_type, context),
            "check_settings": lambda: self._action_profile_settings(client, action_type, context),
            "emoji_status": lambda: self._action_profile_settings(client, action_type, context),
            "drafts": lambda: self._action_profile_settings(client, action_type, context),
            "scheduled_messages": lambda: self._action_profile_settings(
                client, action_type, context
            ),
            "update_profile_gradual": lambda: self._action_profile_settings(
                client, action_type, context
            ),
            "notification_settings": lambda: self._action_profile_settings(
                client, action_type, context
            ),
            "view_story": lambda: self._action_view_story(client, action_type, context),
            "react_to_post": lambda: self._action_react_to_post(client, action_type, context),
            "p2p_send": lambda: self._action_p2p_send(client, action_type, context),
        }
        handler = handlers.get(action_type)
        if handler is None:
            return WarmupActionResult(
                status="unsupported",
                action_type=action_type,
                error_code="action_not_supported_in_passive",
                error_class="contract",
            )
        try:
            return handler()
        except Exception as exc:
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="adapter_raised",
                error_class=exc.__class__.__name__,
                metadata={"message": str(exc)[:200]},
            )

    def _ensure_ready_client(self, account_id: str) -> TdlibClient:
        cached = self._clients.get(account_id)
        if cached is not None:
            return cached
        client = self._client_factory.create(account_id)
        proxy_applied = False
        try:
            deadline_loops = max(1, int(self._config.tdlib_auth_timeout_seconds * 2))
            for _ in range(deadline_loops):
                event = client.receive(self._config.tdlib_receive_timeout_seconds)
                if event is None:
                    continue
                if event.get("@type") == "error":
                    raise _AdapterClientError.from_tdlib_error(event)
                state = extract_authorization_state(event)
                if state is None:
                    continue
                mapped = map_authorization_state(state)
                if mapped.status == TdlibAuthStatus.WAIT_TDLIB_PARAMETERS:
                    client.send(tdlib_parameters_query(self._config, account_id))
                    if not proxy_applied:
                        proxy_applied = apply_account_proxy_to_tdlib(
                            client, account_id, config=self._config
                        )
                    continue
                if mapped.status == TdlibAuthStatus.READY:
                    self._clients[account_id] = client
                    return client
                raise _AdapterClientError(
                    status="runtime_broken",
                    error_code=mapped.recovery_marker or "tdlib_not_ready",
                    error_class="auth_state",
                    message=f"tdlib_auth_status={mapped.status.value}",
                )
            raise _AdapterClientError(
                status="network_error",
                error_code="tdlib_auth_timeout",
                error_class="timeout",
                message="tdlib auth state did not converge",
            )
        except Exception:
            client.close()
            self._clients.pop(account_id, None)
            raise

    def _action_get_me(self, client: TdlibClient, action_type: str) -> WarmupActionResult:
        response = client.send_query({"@type": "getMe"}, self._config.tdlib_receive_timeout_seconds)
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "telegram_user_id_present": response.get("id") is not None,
                "username": response.get("username") or None,
            },
        )

    def _action_ping_proxy(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "proxy_category": context.get("proxy_category"),
                "proxy_status": "reachable",
            },
        )

    def _action_feed_read(self, client: TdlibClient, action_type: str) -> WarmupActionResult:
        chat_ids_result = self._main_chat_ids(client, action_type, 5)
        if isinstance(chat_ids_result, WarmupActionResult):
            return chat_ids_result
        chat_ids = chat_ids_result
        viewed_result = self._view_empty_messages(client, action_type, chat_ids)
        if isinstance(viewed_result, WarmupActionResult):
            return viewed_result
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chats_seen": len(chat_ids),
                "messages_viewed": viewed_result,
            },
        )

    def _action_view_dialogs(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        limit = _bounded_int(context.get("dialog_limit"), minimum=3, maximum=5, default=5)
        chat_ids_result = self._main_chat_ids(client, action_type, limit)
        if isinstance(chat_ids_result, WarmupActionResult):
            return chat_ids_result
        chat_ids = chat_ids_result
        viewed_result = self._view_empty_messages(client, action_type, chat_ids)
        if isinstance(viewed_result, WarmupActionResult):
            return viewed_result
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chats_seen": len(chat_ids),
                "messages_viewed": viewed_result,
            },
        )

    def _action_mark_as_read(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        limit = _bounded_int(context.get("dialog_limit"), minimum=3, maximum=50, default=20)
        chat_ids_result = self._main_chat_ids(client, action_type, limit)
        if isinstance(chat_ids_result, WarmupActionResult):
            return chat_ids_result
        chat_ids = chat_ids_result
        marked_result = self._view_empty_messages(client, action_type, chat_ids)
        if isinstance(marked_result, WarmupActionResult):
            return marked_result
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chats_seen": len(chat_ids),
                "chats_marked": marked_result,
            },
        )

    def _action_search_messages(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        query = str(context.get("search_query") or "")
        limit = _bounded_int(context.get("search_limit"), minimum=1, maximum=20, default=10)
        response = client.send_query(
            {
                "@type": "searchMessages",
                "chat_list": {"@type": "chatListMain"},
                "query": query,
                "offset": "",
                "limit": limit,
                "filter": {"@type": "searchMessagesFilterEmpty"},
                "min_date": 0,
                "max_date": 0,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        messages = response.get("messages")
        results_seen = len(cast(list[object], messages)) if isinstance(messages, list) else 0
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "query": query,
                "results_seen": results_seen,
            },
        )

    def _main_chat_ids(
        self, client: TdlibClient, action_type: str, limit: int
    ) -> list[int] | WarmupActionResult:
        chats_response = client.send_query(
            {"@type": "getChats", "chat_list": {"@type": "chatListMain"}, "limit": limit},
            self._config.tdlib_receive_timeout_seconds,
        )
        if chats_response.get("@type") == "error":
            return _classify_tdlib_error(chats_response, action_type)
        return [int(chat_id) for chat_id in _list_or_empty(chats_response.get("chat_ids"))][:limit]

    def _view_empty_messages(
        self, client: TdlibClient, action_type: str, chat_ids: list[int]
    ) -> int | WarmupActionResult:
        viewed = 0
        for chat_id in chat_ids:
            view_response = client.send_query(
                {
                    "@type": "viewMessages",
                    "chat_id": chat_id,
                    "message_ids": [],
                    "force_read": True,
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if view_response.get("@type") == "error":
                classified = _classify_tdlib_error(view_response, action_type)
                if classified.status == "flood_wait":
                    return classified
                continue
            viewed += 1
        return viewed

    def _required_channel_chat_id(
        self,
        client: TdlibClient,
        action_type: str,
        context: dict[str, Any],
        missing_error_code: str,
    ) -> tuple[str, int] | WarmupActionResult:
        channel_ref = (context.get("channel_ref") or "").strip()
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code=missing_error_code,
                error_class="contract",
            )
        chat_id_result = self._resolve_public_chat_id(client, action_type, channel_ref)
        if isinstance(chat_id_result, WarmupActionResult):
            return chat_id_result
        return channel_ref, chat_id_result

    def _action_channel_browse(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_result = self._required_channel_chat_id(
            client, action_type, context, "channel_browse_missing_channel"
        )
        if isinstance(channel_result, WarmupActionResult):
            return channel_result
        channel_ref, chat_id = channel_result

        opened = client.send_query(
            {"@type": "openChat", "chat_id": chat_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if opened.get("@type") == "error":
            return _classify_tdlib_error(opened, action_type)

        limit = _bounded_int(context.get("history_limit"), minimum=10, maximum=30, default=20)
        history = client.send_query(
            {
                "@type": "getChatHistory",
                "chat_id": chat_id,
                "from_message_id": 0,
                "offset": 0,
                "limit": limit,
                "only_local": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if history.get("@type") == "error":
            return _classify_tdlib_error(history, action_type)

        message_ids = _message_ids(history.get("messages"))
        if message_ids:
            viewed = client.send_query(
                {
                    "@type": "viewMessages",
                    "chat_id": chat_id,
                    "message_ids": message_ids,
                    "force_read": True,
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if viewed.get("@type") == "error":
                return _classify_tdlib_error(viewed, action_type)

        close_response = client.send_query(
            {"@type": "closeChat", "chat_id": chat_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if close_response.get("@type") == "error":
            classified = _classify_tdlib_error(close_response, action_type)
            if classified.status == "flood_wait":
                return classified

        messages_total = len(message_ids)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "chat_id": chat_id,
                "messages_total": messages_total,
                "messages_viewed": messages_total,
                "scroll_depth": round(messages_total / limit, 2) if limit else 0,
            },
        )

    def _action_scroll_channels(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_result = self._required_channel_chat_id(
            client, action_type, context, "scroll_channels_missing_channel"
        )
        if isinstance(channel_result, WarmupActionResult):
            return channel_result
        channel_ref, chat_id = channel_result

        opened = client.send_query(
            {"@type": "openChat", "chat_id": chat_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if opened.get("@type") == "error":
            return _classify_tdlib_error(opened, action_type)

        limit = _bounded_int(context.get("history_limit"), minimum=20, maximum=40, default=30)
        history = client.send_query(
            {
                "@type": "getChatHistory",
                "chat_id": chat_id,
                "from_message_id": 0,
                "offset": 0,
                "limit": limit,
                "only_local": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if history.get("@type") == "error":
            return _classify_tdlib_error(history, action_type)

        message_ids = _message_ids(history.get("messages"))
        viewed_count = 0
        for chunk in _chunks(message_ids, 10):
            viewed = client.send_query(
                {
                    "@type": "viewMessages",
                    "chat_id": chat_id,
                    "message_ids": chunk,
                    "force_read": True,
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if viewed.get("@type") == "error":
                classified = _classify_tdlib_error(viewed, action_type)
                if classified.status == "flood_wait":
                    return classified
                continue
            viewed_count += len(chunk)

        close_response = client.send_query(
            {"@type": "closeChat", "chat_id": chat_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if close_response.get("@type") == "error":
            classified = _classify_tdlib_error(close_response, action_type)
            if classified.status == "flood_wait":
                return classified

        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "chat_id": chat_id,
                "messages_total": len(message_ids),
                "messages_viewed": viewed_count,
                "scroll_depth": round(viewed_count / limit, 2) if limit else 0,
            },
        )

    def _action_vote_poll(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        candidate = self._find_channel_message(
            client,
            action_type,
            context,
            missing_error="vote_poll_missing_channel",
            skip_error="no_open_poll_found",
            predicate=_open_poll_candidate,
        )
        if isinstance(candidate, WarmupActionResult):
            return candidate
        chat_id, channel_ref, message = candidate
        content = _message_content(message)
        options = _poll_option_ids(content)
        if not options:
            return _content_skipped(action_type, "no_open_poll_found", channel_ref)
        chosen_option = options[0]
        response = client.send_query(
            {
                "@type": "setPollAnswer",
                "chat_id": chat_id,
                "message_id": int(message["id"]),
                "option_ids": [chosen_option],
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "chat_id": chat_id,
                "message_id": int(message["id"]),
                "chosen_option": chosen_option,
                "safety_hint": context.get("safety_hint") or "avoid_empty_or_new_accounts",
            },
        )

    def _action_watch_video(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        return self._action_open_media_content(
            client,
            action_type,
            context,
            missing_error="watch_video_missing_channel",
            skip_error="no_video_found",
            predicate=_video_candidate,
        )

    def _action_listen_voice(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        return self._action_open_media_content(
            client,
            action_type,
            context,
            missing_error="listen_voice_missing_channel",
            skip_error="no_voice_found",
            predicate=_voice_candidate,
        )

    def _action_open_media_content(
        self,
        client: TdlibClient,
        action_type: str,
        context: dict[str, Any],
        *,
        missing_error: str,
        skip_error: str,
        predicate: Callable[[dict[str, Any]], bool],
    ) -> WarmupActionResult:
        candidate = self._find_channel_message(
            client,
            action_type,
            context,
            missing_error=missing_error,
            skip_error=skip_error,
            predicate=predicate,
        )
        if isinstance(candidate, WarmupActionResult):
            return candidate
        chat_id, channel_ref, message = candidate
        file_id = _content_file_id(_message_content(message))
        if file_id is None:
            return _content_skipped(action_type, skip_error, channel_ref, {"traffic_heavy": True})
        file_response = client.send_query(
            {"@type": "getFile", "file_id": file_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if file_response.get("@type") == "error":
            return _classify_tdlib_error(file_response, action_type)
        opened = client.send_query(
            {
                "@type": "openMessageContent",
                "chat_id": chat_id,
                "message_id": int(message["id"]),
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if opened.get("@type") == "error":
            return _classify_tdlib_error(opened, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "chat_id": chat_id,
                "message_id": int(message["id"]),
                "file_id": file_id,
                "traffic_heavy": True,
            },
        )

    def _find_channel_message(
        self,
        client: TdlibClient,
        action_type: str,
        context: dict[str, Any],
        *,
        missing_error: str,
        skip_error: str,
        predicate: Callable[[dict[str, Any]], bool],
    ) -> tuple[int, str, dict[str, Any]] | WarmupActionResult:
        channel_ref = (context.get("channel_ref") or "").strip()
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code=missing_error,
                error_class="contract",
            )
        chat_id_result = self._resolve_public_chat_id(client, action_type, channel_ref)
        if isinstance(chat_id_result, WarmupActionResult):
            return chat_id_result
        chat_id = chat_id_result
        limit = _bounded_int(context.get("history_limit"), minimum=5, maximum=50, default=20)
        history = client.send_query(
            {
                "@type": "getChatHistory",
                "chat_id": chat_id,
                "from_message_id": 0,
                "offset": 0,
                "limit": limit,
                "only_local": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if history.get("@type") == "error":
            return _classify_tdlib_error(history, action_type)
        for message in _messages(history.get("messages")):
            if predicate(message):
                return chat_id, channel_ref, message
        metadata = {"traffic_heavy": True} if action_type in {"watch_video", "listen_voice"} else {}
        return _content_skipped(action_type, skip_error, channel_ref, metadata)

    def _action_search_gif(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        query = str(context.get("search_query") or "cat")
        response = client.send_query(
            {"@type": "searchAnimations", "query": query, "offset": "", "limit": 10},
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        file_ids = _animation_file_ids(response.get("animations"))[:3]
        touched = 0
        for file_id in file_ids:
            file_response = client.send_query(
                {"@type": "getFile", "file_id": file_id},
                self._config.tdlib_receive_timeout_seconds,
            )
            if file_response.get("@type") == "error":
                classified = _classify_tdlib_error(file_response, action_type)
                if classified.status == "flood_wait":
                    return classified
                continue
            touched += 1
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "query": query,
                "animations_seen": len(file_ids),
                "files_touched": touched,
                "traffic_heavy": True,
            },
        )

    def _action_view_stickers(self, client: TdlibClient, action_type: str) -> WarmupActionResult:
        response = client.send_query(
            {"@type": "getRecentStickers", "is_attached": False},
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        set_ids = _sticker_set_ids(response.get("stickers"))[:3]
        viewed = 0
        for set_id in set_ids:
            set_response = client.send_query(
                {"@type": "getStickerSet", "set_id": set_id},
                self._config.tdlib_receive_timeout_seconds,
            )
            if set_response.get("@type") == "error":
                classified = _classify_tdlib_error(set_response, action_type)
                if classified.status == "flood_wait":
                    return classified
                continue
            viewed += 1
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "stickers_seen": len(set_ids),
                "sets_viewed": viewed,
                "traffic_heavy": True,
            },
        )

    def _action_inline_bot(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        bot_username = str(context.get("inline_bot_username") or "@gif")
        if bot_username not in {"@gif", "@pic", "@sticker", "@vid"}:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="inline_bot_not_approved",
                error_class="safety",
                metadata={"bot_username": bot_username, "traffic_heavy": True},
            )
        bot = client.send_query(
            {"@type": "searchPublicChat", "username": bot_username.lstrip("@")},
            self._config.tdlib_receive_timeout_seconds,
        )
        if bot.get("@type") == "error":
            return _classify_tdlib_error(bot, action_type)
        bot_user_id = bot.get("id")
        if bot_user_id is None:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="inline_bot_not_found",
                error_class="content",
                metadata={"bot_username": bot_username, "traffic_heavy": True},
            )
        response = client.send_query(
            {
                "@type": "getInlineQueryResults",
                "bot_user_id": int(bot_user_id),
                "chat_id": int(context.get("inline_chat_id") or 0),
                "query": str(context.get("inline_query") or "cat"),
                "offset": "",
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        results = response.get("results")
        result_items = cast(list[object], results) if isinstance(results, list) else []
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "bot_username": bot_username,
                "query": str(context.get("inline_query") or "cat"),
                "results_seen": len(result_items),
                "traffic_heavy": True,
            },
        )

    def _action_link_preview(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        url = str(context.get("preview_url") or "https://example.com/")
        response = client.send_query(
            {"@type": "getWebPagePreview", "text": url},
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "preview_url": url,
                "has_preview": response.get("@type") != "error",
                "traffic_heavy": True,
            },
        )

    def _action_forward_message(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_ref = (context.get("channel_ref") or "").strip()
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="forward_message_missing_channel",
                error_class="contract",
            )
        from_chat_result = self._resolve_public_chat_id(client, action_type, channel_ref)
        if isinstance(from_chat_result, WarmupActionResult):
            return from_chat_result
        from_chat_id = from_chat_result
        history = client.send_query(
            {
                "@type": "getChatHistory",
                "chat_id": from_chat_id,
                "from_message_id": 0,
                "offset": 0,
                "limit": _bounded_int(
                    context.get("history_limit"), minimum=1, maximum=30, default=10
                ),
                "only_local": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if history.get("@type") == "error":
            return _classify_tdlib_error(history, action_type)
        message_ids = _message_ids(history.get("messages"))
        if not message_ids:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="no_forward_source_available",
                error_class="content",
                metadata={"channel_ref": channel_ref},
            )
        saved_chat_id = self._saved_messages_chat_id(client, action_type)
        if isinstance(saved_chat_id, WarmupActionResult):
            return saved_chat_id
        forwarded = client.send_query(
            {
                "@type": "forwardMessages",
                "from_chat_id": from_chat_id,
                "chat_id": saved_chat_id,
                "message_ids": [message_ids[0]],
                "disable_notification": True,
                "protect_content": False,
                "send_copy": False,
                "remove_caption": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if forwarded.get("@type") == "error":
            return _classify_tdlib_error(forwarded, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "from_chat_id": from_chat_id,
                "to_chat": "saved_messages",
                "to_chat_id": saved_chat_id,
                "message_id": message_ids[0],
            },
        )

    def _action_saved_messages(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        text = str(context.get("note_text") or "remember")
        saved_chat_id = self._saved_messages_chat_id(client, action_type)
        if isinstance(saved_chat_id, WarmupActionResult):
            return saved_chat_id
        sent = client.send_query(
            {
                "@type": "sendMessage",
                "chat_id": saved_chat_id,
                "input_message_content": {
                    "@type": "inputMessageText",
                    "text": {"@type": "formattedText", "text": text},
                },
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if sent.get("@type") == "error":
            return _classify_tdlib_error(sent, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "to_chat": "saved_messages",
                "to_chat_id": saved_chat_id,
                "text_length": len(text),
            },
        )

    def _action_sync_contacts(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        contacts = client.send_query(
            {"@type": "getContacts"},
            self._config.tdlib_receive_timeout_seconds,
        )
        if contacts.get("@type") == "error":
            return _classify_tdlib_error(contacts, action_type)
        contacts_pool = list(context.get("contacts_pool") or [])
        if not contacts_pool:
            raw_user_ids = contacts.get("user_ids")
            existing_contacts = (
                cast(list[object], raw_user_ids) if isinstance(raw_user_ids, list) else []
            )
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="no_contacts_pool_available",
                error_class="content",
                metadata={"existing_contacts": len(existing_contacts)},
            )
        imported = client.send_query(
            {"@type": "importContacts", "contacts": contacts_pool},
            self._config.tdlib_receive_timeout_seconds,
        )
        if imported.get("@type") == "error":
            return _classify_tdlib_error(imported, action_type)
        imported_user_ids = imported.get("user_ids")
        imported_contacts = (
            cast(list[object], imported_user_ids)
            if isinstance(imported_user_ids, list)
            else contacts_pool
        )
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "contacts_imported": len(imported_contacts),
            },
        )

    def _action_archive_chat(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        chat_id_result = self._select_unprotected_chat_id(client, action_type, context)
        if isinstance(chat_id_result, WarmupActionResult):
            return chat_id_result
        chat_id = chat_id_result
        archived = client.send_query(
            {
                "@type": "addChatToList",
                "chat_id": chat_id,
                "chat_list": {"@type": "chatListArchive"},
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if archived.get("@type") == "error":
            return _classify_tdlib_error(archived, action_type)
        temporary = bool(context.get("temporary", False))
        reversed_ok = False
        if temporary:
            restored = client.send_query(
                {
                    "@type": "addChatToList",
                    "chat_id": chat_id,
                    "chat_list": {"@type": "chatListMain"},
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if restored.get("@type") == "error":
                classified = _classify_tdlib_error(restored, action_type)
                if classified.status == "flood_wait":
                    return classified
            else:
                reversed_ok = True
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chat_id": chat_id,
                "archived": True,
                "temporary": temporary,
                "reversed": reversed_ok,
            },
        )

    def _action_mute_chat(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        chat_id_result = self._select_unprotected_chat_id(client, action_type, context)
        if isinstance(chat_id_result, WarmupActionResult):
            return chat_id_result
        chat_id = chat_id_result
        mute_for_seconds = _bounded_int(
            context.get("mute_for_seconds"), minimum=1, maximum=604_800, default=86_400
        )
        muted = client.send_query(
            _set_chat_mute_query(chat_id, mute_for_seconds),
            self._config.tdlib_receive_timeout_seconds,
        )
        if muted.get("@type") == "error":
            return _classify_tdlib_error(muted, action_type)
        temporary = bool(context.get("temporary", False))
        reversed_ok = False
        if temporary:
            restored = client.send_query(
                _set_chat_mute_query(chat_id, 0),
                self._config.tdlib_receive_timeout_seconds,
            )
            if restored.get("@type") == "error":
                classified = _classify_tdlib_error(restored, action_type)
                if classified.status == "flood_wait":
                    return classified
            else:
                reversed_ok = True
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chat_id": chat_id,
                "mute_for_seconds": mute_for_seconds,
                "temporary": temporary,
                "reversed": reversed_ok,
            },
        )

    def _select_unprotected_chat_id(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> int | WarmupActionResult:
        explicit_chat_id = context.get("chat_id")
        if explicit_chat_id is not None:
            chat_id = int(explicit_chat_id)
            if _is_protected_chat_id(chat_id):
                return _protected_chat_result(action_type, chat_id)
            return chat_id
        response = client.send_query(
            {
                "@type": "getChats",
                "chat_list": {"@type": "chatListMain"},
                "limit": _bounded_int(context.get("chat_limit"), minimum=1, maximum=50, default=20),
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if response.get("@type") == "error":
            return _classify_tdlib_error(response, action_type)
        raw_chat_ids = response.get("chat_ids")
        chat_ids = cast(list[object], raw_chat_ids) if isinstance(raw_chat_ids, list) else []
        for raw_chat_id in chat_ids:
            if not isinstance(raw_chat_id, int | str):
                continue
            chat_id = int(raw_chat_id)
            if not _is_protected_chat_id(chat_id):
                return chat_id
        return _protected_chat_result(action_type, 0)

    def _action_profile_settings(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        if action_type == "simulate_typing":
            chat_id_result = self._resolve_context_chat_id(client, action_type, context)
            if isinstance(chat_id_result, WarmupActionResult):
                return chat_id_result
            duration = _bounded_int(
                context.get("typing_duration_seconds"), minimum=3, maximum=8, default=5
            )
            response = client.send_query(
                {
                    "@type": "sendChatAction",
                    "chat_id": chat_id_result,
                    "action": {"@type": "chatActionTyping"},
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "chat_id": chat_id_result,
                    "typing_duration_seconds": duration,
                },
            )
        if action_type == "view_profile":
            user_id_result = self._resolve_profile_user_id(client, action_type, context)
            if isinstance(user_id_result, WarmupActionResult):
                return user_id_result
            response = client.send_query(
                {"@type": "getUser", "user_id": user_id_result},
                self._config.tdlib_receive_timeout_seconds,
            )
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={"provider": self.provider_name, "user_id": user_id_result},
            )
        if action_type == "check_settings":
            option_name = str(context.get("option_name") or "notification_group_count_max")
            response = client.send_query(
                {"@type": "getOption", "name": option_name},
                self._config.tdlib_receive_timeout_seconds,
            )
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={"provider": self.provider_name, "option_name": option_name},
            )
        if action_type == "emoji_status":
            if context.get("is_premium") is False:
                return WarmupActionResult(
                    status="skipped",
                    action_type=action_type,
                    error_code="non_premium_account",
                    error_class="capability",
                )
            emoji_id = str(context.get("emoji_id") or "🙂")
            response = client.send_query(
                {"@type": "setEmojiStatus", "emoji_status": {"custom_emoji_id": emoji_id}},
                self._config.tdlib_receive_timeout_seconds,
            )
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={"provider": self.provider_name, "emoji_id": emoji_id},
            )
        if action_type == "drafts":
            chat_id_result = self._resolve_context_chat_id(client, action_type, context)
            if isinstance(chat_id_result, WarmupActionResult):
                return chat_id_result
            draft_text = str(context.get("draft_text") or "todo")
            response = client.send_query(
                _set_draft_query(chat_id_result, draft_text),
                self._config.tdlib_receive_timeout_seconds,
            )
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            cleared = False
            if bool(context.get("temporary", True)):
                clear = client.send_query(
                    {
                        "@type": "setChatDraftMessage",
                        "chat_id": chat_id_result,
                        "draft_message": None,
                    },
                    self._config.tdlib_receive_timeout_seconds,
                )
                if clear.get("@type") == "error":
                    classified = _classify_tdlib_error(clear, action_type)
                    if classified.status == "flood_wait":
                        return classified
                else:
                    cleared = True
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "chat_id": chat_id_result,
                    "draft_length": len(draft_text),
                    "cleared": cleared,
                },
            )
        if action_type == "scheduled_messages":
            saved_chat_id = self._saved_messages_chat_id(client, action_type)
            if isinstance(saved_chat_id, WarmupActionResult):
                return saved_chat_id
            text = str(context.get("note_text") or "remember")
            sent = client.send_query(
                {
                    "@type": "sendMessage",
                    "chat_id": saved_chat_id,
                    "input_message_content": {
                        "@type": "inputMessageText",
                        "text": {"@type": "formattedText", "text": text},
                    },
                    "scheduling_state": {
                        "@type": "messageSchedulingStateSendAtDate",
                        "send_date": int(context.get("schedule_at") or 1_800_000_000),
                    },
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if sent.get("@type") == "error":
                return _classify_tdlib_error(sent, action_type)
            message_id = int(sent.get("id") or 0)
            rescheduled = False
            if bool(context.get("temporary", True)) and message_id:
                edited = client.send_query(
                    {
                        "@type": "editMessageSchedulingState",
                        "chat_id": saved_chat_id,
                        "message_id": message_id,
                        "scheduling_state": None,
                    },
                    self._config.tdlib_receive_timeout_seconds,
                )
                if edited.get("@type") == "error":
                    classified = _classify_tdlib_error(edited, action_type)
                    if classified.status == "flood_wait":
                        return classified
                else:
                    rescheduled = True
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "to_chat": "saved_messages",
                    "message_id": message_id,
                    "rescheduled": rescheduled,
                },
            )
        if action_type == "update_profile_gradual":
            profile_field = str(context.get("profile_field") or "bio")
            if profile_field == "name":
                response = client.send_query(
                    {
                        "@type": "setName",
                        "first_name": str(context.get("first_name") or "Alex"),
                        "last_name": str(context.get("last_name") or ""),
                    },
                    self._config.tdlib_receive_timeout_seconds,
                )
            else:
                response = client.send_query(
                    {"@type": "setBio", "bio": str(context.get("bio") or "reading")},
                    self._config.tdlib_receive_timeout_seconds,
                )
                profile_field = "bio"
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={"provider": self.provider_name, "profile_field": profile_field},
            )
        if action_type == "notification_settings":
            scope_name = str(context.get("notification_scope") or "private")
            response = client.send_query(
                {
                    "@type": "setScopeNotificationSettings",
                    "scope": _notification_scope(scope_name),
                    "notification_settings": {
                        "@type": "scopeNotificationSettings",
                        "mute_for": int(context.get("mute_for_seconds") or 0),
                    },
                },
                self._config.tdlib_receive_timeout_seconds,
            )
            if response.get("@type") == "error":
                return _classify_tdlib_error(response, action_type)
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={"provider": self.provider_name, "notification_scope": scope_name},
            )
        return WarmupActionResult(
            status="unsupported",
            action_type=action_type,
            error_code="action_not_supported_in_passive",
            error_class="contract",
        )

    def _resolve_context_chat_id(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> int | WarmupActionResult:
        if context.get("chat_id") is not None:
            return int(context["chat_id"])
        channel_ref = (context.get("channel_ref") or "").strip()
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="profile_action_missing_chat",
                error_class="contract",
            )
        return self._resolve_public_chat_id(client, action_type, channel_ref)

    def _resolve_profile_user_id(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> int | WarmupActionResult:
        if context.get("user_id") is not None:
            return int(context["user_id"])
        contacts = client.send_query(
            {"@type": "getContacts"},
            self._config.tdlib_receive_timeout_seconds,
        )
        if contacts.get("@type") == "error":
            return _classify_tdlib_error(contacts, action_type)
        user_ids = contacts.get("user_ids")
        contact_user_ids = cast(list[object], user_ids) if isinstance(user_ids, list) else []
        if contact_user_ids and isinstance(contact_user_ids[0], int | str):
            return int(contact_user_ids[0])
        return WarmupActionResult(
            status="skipped",
            action_type=action_type,
            error_code="no_profile_user_available",
            error_class="content",
        )

    def _action_view_story(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_result = self._required_channel_chat_id(
            client, action_type, context, "view_story_missing_channel"
        )
        if isinstance(channel_result, WarmupActionResult):
            return channel_result
        channel_ref, chat_id = channel_result

        stories = client.send_query(
            {"@type": "getChatActiveStories", "chat_id": chat_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if stories.get("@type") == "error":
            return _classify_tdlib_error(stories, action_type)

        active_stories = [
            cast(dict[str, Any], story)
            for story in _list_or_empty(stories.get("stories"))
            if isinstance(story, dict)
        ]
        if not active_stories:
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "channel_ref": channel_ref,
                    "chat_id": chat_id,
                    "viewed_count": 0,
                    "has_stories": False,
                },
            )

        viewed = 0
        for story in active_stories[:3]:
            story_id = story.get("id")
            if story_id is None:
                continue
            opened = client.send_query(
                {"@type": "openStory", "chat_id": chat_id, "story_id": story_id},
                self._config.tdlib_receive_timeout_seconds,
            )
            if opened.get("@type") == "error":
                classified = _classify_tdlib_error(opened, action_type)
                if classified.status == "flood_wait":
                    return classified
                continue
            viewed += 1

        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "chat_id": chat_id,
                "viewed_count": viewed,
                "has_stories": True,
            },
        )

    def _action_react_to_post(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_result = self._required_channel_chat_id(
            client, action_type, context, "react_to_post_missing_channel"
        )
        if isinstance(channel_result, WarmupActionResult):
            return channel_result
        channel_ref, chat_id = channel_result

        history = client.send_query(
            {
                "@type": "getChatHistory",
                "chat_id": chat_id,
                "from_message_id": 0,
                "offset": 0,
                "limit": 5,
                "only_local": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if history.get("@type") == "error":
            return _classify_tdlib_error(history, action_type)
        message_ids = _message_ids(history.get("messages"))
        if not message_ids:
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "channel_ref": channel_ref,
                    "chat_id": chat_id,
                    "reacted": False,
                    "reason": "no_messages",
                },
            )

        message_id = message_ids[0]
        available = client.send_query(
            {
                "@type": "getMessageAvailableReactions",
                "chat_id": chat_id,
                "message_id": message_id,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if available.get("@type") == "error":
            return _classify_tdlib_error(available, action_type)
        reactions = _available_reactions(available.get("reactions"))
        if not reactions:
            reactions = [
                str(value) for value in _list_or_empty(context.get("available_reactions")) if value
            ]
        if not reactions:
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "channel_ref": channel_ref,
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "has_reactions": False,
                    "reacted": False,
                },
            )

        reaction = reactions[0]
        added = client.send_query(
            {
                "@type": "addMessageReaction",
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction_type": _emoji_reaction_type(reaction),
                "is_big": False,
                "update_recent_reactions": False,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if added.get("@type") == "error":
            return _classify_tdlib_error(added, action_type)

        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "channel_ref": channel_ref,
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": reaction,
                "has_reactions": True,
                "available_reactions": reactions,
                "reacted": True,
            },
        )

    def _action_join_chat(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        chat_target = (context.get("chat_target") or "").strip()
        if not chat_target:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="join_chat_missing_target",
                error_class="contract",
            )
        username = chat_target.lstrip("@")
        search = client.send_query(
            {"@type": "searchPublicChat", "username": username},
            self._config.tdlib_receive_timeout_seconds,
        )
        if search.get("@type") == "error":
            return _classify_tdlib_error(search, action_type)
        chat_id = search.get("id")
        if chat_id is None:
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="public_chat_not_found",
                error_class="contract",
                metadata={"chat_target": chat_target},
            )
        join = client.send_query(
            {"@type": "joinChat", "chat_id": chat_id},
            self._config.tdlib_receive_timeout_seconds,
        )
        if join.get("@type") == "error":
            return _classify_tdlib_error(join, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chat_target": chat_target,
                "joined_chat_id": chat_id,
            },
        )

    def _resolve_public_chat_id(
        self, client: TdlibClient, action_type: str, channel_ref: str
    ) -> int | WarmupActionResult:
        search = client.send_query(
            {"@type": "searchPublicChat", "username": channel_ref.lstrip("@")},
            self._config.tdlib_receive_timeout_seconds,
        )
        if search.get("@type") == "error":
            return _classify_tdlib_error(search, action_type)
        chat_id = search.get("id")
        if chat_id is None:
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="public_chat_not_found",
                error_class="contract",
                metadata={"channel_ref": channel_ref},
            )
        return int(chat_id)

    def _saved_messages_chat_id(
        self, client: TdlibClient, action_type: str
    ) -> int | WarmupActionResult:
        me = client.send_query({"@type": "getMe"}, self._config.tdlib_receive_timeout_seconds)
        if me.get("@type") == "error":
            return _classify_tdlib_error(me, action_type)
        user_id = me.get("id")
        if user_id is None:
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="saved_messages_user_missing",
                error_class="contract",
            )
        chat = client.send_query(
            {"@type": "createPrivateChat", "user_id": int(user_id), "force": True},
            self._config.tdlib_receive_timeout_seconds,
        )
        if chat.get("@type") == "error":
            return _classify_tdlib_error(chat, action_type)
        chat_id = chat.get("id")
        if chat_id is None:
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="saved_messages_chat_missing",
                error_class="contract",
            )
        return int(chat_id)

    def _action_p2p_send(
        self, client: TdlibClient, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        peer_telegram_id = context.get("peer_telegram_user_id")
        text = context.get("text")
        if not peer_telegram_id or not text:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="p2p_send_missing_context",
                error_class="contract",
            )
        chat_lookup = client.send_query(
            {"@type": "createPrivateChat", "user_id": int(peer_telegram_id), "force": False},
            self._config.tdlib_receive_timeout_seconds,
        )
        if chat_lookup.get("@type") == "error":
            return _classify_tdlib_error(chat_lookup, action_type)
        chat_id = chat_lookup.get("id")
        if chat_id is None:
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="private_chat_not_resolved",
                error_class="contract",
            )
        typing_duration = compute_typing_duration(
            len(str(text)),
            personality_seed=_personality_seed(context),
            rng=random.Random(str(context.get("text_seed") or "")),
        )
        typing_started = False
        typing_error_code: str | None = None
        typing_response = client.send_query(
            {
                "@type": "sendChatAction",
                "chat_id": chat_id,
                "action": {"@type": "chatActionTyping"},
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if typing_response.get("@type") == "error":
            typing_error_code = str(typing_response.get("message") or "send_chat_action_error")
        else:
            typing_started = True
        time.sleep(typing_duration)
        send = client.send_query(
            {
                "@type": "sendMessage",
                "chat_id": chat_id,
                "input_message_content": {
                    "@type": "inputMessageText",
                    "text": {"@type": "formattedText", "text": text},
                },
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if send.get("@type") == "error":
            return _classify_tdlib_error(send, action_type)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "peer_telegram_user_id": peer_telegram_id,
                "peer_account_id": context.get("peer_account_id"),
                "chat_id": chat_id,
                "text_seed": context.get("text_seed"),
                "text_length": len(text),
                "typing_started": typing_started,
                "typing_duration_ms": int(typing_duration * 1000),
                "typing_error_code": typing_error_code,
            },
        )


def _personality_seed(context: dict[str, Any]) -> dict[str, Any]:
    raw = context.get("personality_seed")
    return cast(dict[str, Any], raw) if isinstance(raw, dict) else {}


def _bounded_int(value: Any, *, minimum: int, maximum: int, default: int) -> int:
    try:
        parsed = int(value)
    except _INT_COERCION_ERRORS:
        parsed = default
    return min(maximum, max(minimum, parsed))


def _list_or_empty(value: Any) -> list[Any]:
    return cast(list[Any], value) if isinstance(value, list) else []


def _message_ids(raw_messages: Any) -> list[int]:
    out: list[int] = []
    for raw_message in _list_or_empty(raw_messages):
        if not isinstance(raw_message, dict):
            continue
        message = cast(dict[str, Any], raw_message)
        message_id = message.get("id")
        if message_id is None:
            continue
        out.append(int(message_id))
    return out


def _messages(raw_messages: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_messages, list):
        return []
    return [
        cast(dict[str, Any], message)
        for message in cast(list[Any], raw_messages)
        if isinstance(message, dict)
    ]


def _message_content(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("content")
    return cast(dict[str, Any], content) if isinstance(content, dict) else {}


def _open_poll_candidate(message: dict[str, Any]) -> bool:
    content = _message_content(message)
    if content.get("@type") != "messagePoll":
        return False
    poll = content.get("poll")
    if isinstance(poll, dict) and cast(dict[str, Any], poll).get("is_closed") is True:
        return False
    return bool(_poll_option_ids(content))


def _video_candidate(message: dict[str, Any]) -> bool:
    content = _message_content(message)
    return content.get("@type") == "messageVideo" and _content_file_id(content) is not None


def _voice_candidate(message: dict[str, Any]) -> bool:
    content = _message_content(message)
    return content.get("@type") in {"messageVoiceNote", "messageAudio"} and (
        _content_file_id(content) is not None
    )


def _poll_option_ids(content: dict[str, Any]) -> list[str]:
    poll = content.get("poll")
    if not isinstance(poll, dict):
        return []
    poll_data = cast(dict[str, Any], poll)
    options = poll_data.get("options")
    if not isinstance(options, list):
        return []
    out: list[str] = []
    for index, option in enumerate(cast(list[Any], options)):
        if not isinstance(option, dict):
            continue
        option_data = cast(dict[str, Any], option)
        value = option_data.get("id") or option_data.get("data") or option_data.get("option_id")
        out.append(str(value if value is not None else index))
    return out


def _content_file_id(content: dict[str, Any]) -> int | None:
    for path in (
        ("video", "video", "id"),
        ("voice_note", "voice", "id"),
        ("audio", "audio", "id"),
    ):
        value: Any = content
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = cast(dict[str, Any], value).get(key)
        if value is not None:
            return int(value)
    return None


def _animation_file_ids(raw_animations: Any) -> list[int]:
    if not isinstance(raw_animations, list):
        return []
    out: list[int] = []
    for item in cast(list[object], raw_animations):
        if not isinstance(item, dict):
            continue
        animation = cast(dict[str, object], item)
        value = animation.get("file_id") or animation.get("id")
        nested = animation.get("animation")
        if value is None and isinstance(nested, dict):
            nested_animation = cast(dict[str, object], nested)
            value = nested_animation.get("id")
            file_obj = nested_animation.get("animation")
            if value is None and isinstance(file_obj, dict):
                value = cast(dict[str, object], file_obj).get("id")
        if isinstance(value, int | str):
            out.append(int(value))
    return out


def _sticker_set_ids(raw_stickers: Any) -> list[int]:
    if not isinstance(raw_stickers, list):
        return []
    out: list[int] = []
    for sticker in cast(list[object], raw_stickers):
        if not isinstance(sticker, dict):
            continue
        sticker_data = cast(dict[str, object], sticker)
        value = sticker_data.get("set_id") or sticker_data.get("setId")
        if isinstance(value, int | str):
            out.append(int(value))
    return list(dict.fromkeys(out))


def _content_skipped(
    action_type: str, error_code: str, channel_ref: str, metadata: dict[str, Any] | None = None
) -> WarmupActionResult:
    return WarmupActionResult(
        status="skipped",
        action_type=action_type,
        error_code=error_code,
        error_class="content",
        metadata={"channel_ref": channel_ref, **(metadata or {})},
    )


def _is_protected_chat_id(chat_id: int) -> bool:
    return chat_id >= 0 or chat_id == 777000


def _protected_chat_result(action_type: str, chat_id: int) -> WarmupActionResult:
    return WarmupActionResult(
        status="skipped",
        action_type=action_type,
        error_code="protected_chat",
        error_class="safety",
        metadata={"chat_id": chat_id},
    )


def _set_chat_mute_query(chat_id: int, mute_for_seconds: int) -> dict[str, Any]:
    return {
        "@type": "setChatNotificationSettings",
        "chat_id": chat_id,
        "notification_settings": {
            "@type": "chatNotificationSettings",
            "mute_for": mute_for_seconds,
        },
    }


def _set_draft_query(chat_id: int, draft_text: str) -> dict[str, Any]:
    return {
        "@type": "setChatDraftMessage",
        "chat_id": chat_id,
        "draft_message": {
            "@type": "draftMessage",
            "input_message_text": {
                "@type": "inputMessageText",
                "text": {"@type": "formattedText", "text": draft_text},
            },
        },
    }


def _notification_scope(scope_name: str) -> dict[str, str]:
    mapping = {
        "private": "notificationSettingsScopePrivateChats",
        "group": "notificationSettingsScopeGroupChats",
        "channel": "notificationSettingsScopeChannelChats",
    }
    return {"@type": mapping.get(scope_name, "notificationSettingsScopePrivateChats")}


def _chunks(values: list[int], size: int) -> list[list[int]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _available_reactions(raw_reactions: Any) -> list[str]:
    out: list[str] = []
    for raw_reaction in _list_or_empty(raw_reactions):
        if isinstance(raw_reaction, str) and raw_reaction:
            out.append(raw_reaction)
            continue
        if not isinstance(raw_reaction, dict):
            continue
        raw = cast(dict[str, Any], raw_reaction)
        value = raw.get("emoji")
        if isinstance(value, str) and value:
            out.append(value)
            continue
        nested = raw.get("type") or raw.get("reaction_type")
        if isinstance(nested, dict):
            value = cast(dict[str, Any], nested).get("emoji")
            if isinstance(value, str) and value:
                out.append(value)
    return out


def _emoji_reaction_type(emoji: str) -> dict[str, str]:
    return {"@type": "reactionTypeEmoji", "emoji": emoji}
