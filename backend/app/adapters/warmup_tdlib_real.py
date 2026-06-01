from __future__ import annotations

# pyright: reportPrivateUsage=false

import logging
from collections.abc import Callable
from typing import Any

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
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib


_logger = logging.getLogger(__name__)


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
            "join_chat": lambda: self._action_join_chat(client, action_type, context),
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
        chats_response = client.send_query(
            {
                "@type": "getChats",
                "chat_list": {"@type": "chatListMain"},
                "limit": 5,
            },
            self._config.tdlib_receive_timeout_seconds,
        )
        if chats_response.get("@type") == "error":
            return _classify_tdlib_error(chats_response, action_type)
        chat_ids = list(chats_response.get("chat_ids") or [])[:5]
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
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "chats_seen": len(chat_ids),
                "messages_viewed": viewed,
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
            },
        )
