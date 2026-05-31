"""Phase 2/3/4 warmup TDLib adapter.

Контракт по слоям:
- `passive` (Phase 2): только read-only — `get_me`, `feed_read`, `ping_proxy`.
- `network` (Phase 3): passive + safe-write `join_chat` (поиск+джойн
  публичного канала из `strategy.target_channels_json`).
- `advanced` (Phase 4): network + write `p2p_send` (личное сообщение
  trusted-peer'у; текст приходит из `WarmupTextProvider`).

Каждый action возвращает структурированный `WarmupActionResult`. Адаптер
обязан НЕ кидать исключения — диспетчер защищён `_execute_passive_action`,
но мы стараемся гасить ошибки на уровне адаптера, чтобы не разрушать стек
вызовов.

Lifecycle: `RealWarmupTdlibAdapter` поддерживает кэш TDLib-клиентов на один
dispatch tick. Диспетчер обязан вызвать `adapter.close()` в `finally` —
поэтому метод присутствует на всех реализациях (no-op для Mock/Unavailable).
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibAuthStatus,
    TdlibClient,
    TdlibClientFactory,
    UnavailableTdlibClientFactory,
    extract_authorization_state,
    map_authorization_state,
    map_tdlib_error,
    tdlib_parameters_query,
)
from app.config import Settings, settings
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib

_logger = logging.getLogger(__name__)


# Поддерживаемые action_type'ы с разбивкой по execution_mode. Используется
# и dispatch'ем (gate per session), и фактори (для отчётов).
SUPPORTED_PASSIVE_ACTIONS: tuple[str, ...] = ("feed_read", "ping_proxy", "get_me")
SUPPORTED_NETWORK_ACTIONS: tuple[str, ...] = SUPPORTED_PASSIVE_ACTIONS + ("join_chat",)
SUPPORTED_ADVANCED_ACTIONS: tuple[str, ...] = SUPPORTED_NETWORK_ACTIONS + ("p2p_send",)

SUPPORTED_ACTIONS_BY_MODE: dict[str, tuple[str, ...]] = {
    "passive": SUPPORTED_PASSIVE_ACTIONS,
    "network": SUPPORTED_NETWORK_ACTIONS,
    "advanced": SUPPORTED_ADVANCED_ACTIONS,
}

WRITE_ACTION_TYPES: frozenset[str] = frozenset({"join_chat", "p2p_send"})


def collect_supported_actions(modes: tuple[str, ...]) -> set[str]:
    out: set[str] = set()
    for mode in modes:
        out.update(SUPPORTED_ACTIONS_BY_MODE.get(mode, ()))
    return out


@dataclass(frozen=True)
class WarmupActionResult:
    """Структурированный исход одного action-вызова.

    `status` — единственное поле, по которому диспетчер принимает решения:
    "ok"/"flood_wait"/"network_error"/"runtime_broken"/"unsupported"/
    "unavailable"/"not_implemented"/"missing_context".
    """

    status: str
    action_type: str
    metadata: dict[str, Any] = field(default_factory=lambda: {})
    error_class: str | None = None
    error_code: str | None = None
    retry_after_seconds: int | None = None

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


class WarmupTdlibAdapter(Protocol):
    """Минимальная поверхность, которую consume'ит warmup_dispatch."""

    provider_name: str

    def is_available(self) -> bool: ...

    def supports_action(self, action_type: str) -> bool: ...

    def execute_action(
        self, *, account_id: str, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult: ...

    def close(self) -> None: ...


# ---------------------------------------------------------------------------
# Mock implementation
# ---------------------------------------------------------------------------


class MockWarmupTdlibAdapter:
    """Детерминированный мок для тестов и локального dev.

    Без сетевых вызовов. RNG seed гарантирует воспроизводимое поведение.
    Поддерживает:
    - `get_me`/`feed_read`/`ping_proxy` (Phase 2).
    - `join_chat` (Phase 3) — требует context["chat_target"], имитирует
      поиск + джойн публичного канала.
    - `p2p_send` (Phase 4) — требует context["peer_account_id"] и
      context["text"], имитирует отправку личного сообщения.

    `failure_action_types` принудительно превращает указанные action'ы в
    failure (для покрытия circuit-breaker и flood_wait).
    """

    provider_name = "mock"

    def __init__(
        self,
        *,
        rng_seed: int = 0,
        failure_action_types: tuple[str, ...] = (),
        failure_status: str = "network_error",
        failure_retry_after_seconds: int | None = None,
        supported_modes: tuple[str, ...] = ("passive", "network", "advanced"),
    ) -> None:
        self._rng = random.Random(rng_seed)
        self._failures = set(failure_action_types)
        self._failure_status = failure_status
        self._failure_retry_after = failure_retry_after_seconds
        self._supported = collect_supported_actions(supported_modes)
        self.calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return True

    def supports_action(self, action_type: str) -> bool:
        return action_type in self._supported

    def close(self) -> None:  # mock has nothing to close
        return None

    def execute_action(
        self, *, account_id: str, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        self.calls.append(
            {"account_id": account_id, "action_type": action_type, "context": dict(context)}
        )
        if not self.supports_action(action_type):
            return WarmupActionResult(
                status="unsupported",
                action_type=action_type,
                error_code="action_not_supported_in_passive",
                error_class="contract",
            )
        if action_type in self._failures:
            return WarmupActionResult(
                status=self._failure_status,
                action_type=action_type,
                error_code="mock_forced_failure",
                error_class="mock",
                retry_after_seconds=self._failure_retry_after,
            )
        if action_type == "join_chat":
            chat_target = context.get("chat_target")
            if not chat_target:
                return WarmupActionResult(
                    status="missing_context",
                    action_type=action_type,
                    error_code="join_chat_missing_target",
                    error_class="contract",
                )
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "latency_ms": self._rng.randint(80, 240),
                    "chat_target": chat_target,
                    "joined_chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                },
            )
        if action_type == "p2p_send":
            peer_id = context.get("peer_account_id")
            text = context.get("text")
            if not peer_id or not text:
                return WarmupActionResult(
                    status="missing_context",
                    action_type=action_type,
                    error_code="p2p_send_missing_context",
                    error_class="contract",
                )
            return WarmupActionResult(
                status="ok",
                action_type=action_type,
                metadata={
                    "provider": self.provider_name,
                    "latency_ms": self._rng.randint(60, 200),
                    "peer_account_id": peer_id,
                    "text_seed": context.get("text_seed"),
                    "text_length": len(text),
                },
            )
        # Phase 2 read-only branches
        latency_ms = self._rng.randint(40, 180)
        metadata: dict[str, Any] = {
            "latency_ms": latency_ms,
            "provider": self.provider_name,
        }
        if action_type == "feed_read":
            metadata["chats_seen"] = self._rng.randint(1, 5)
            metadata["messages_viewed"] = self._rng.randint(0, 4)
        elif action_type == "ping_proxy":
            metadata["proxy_category"] = context.get("proxy_category")
            metadata["proxy_status"] = "reachable"
        elif action_type == "get_me":
            metadata["telegram_user_id_present"] = True
        return WarmupActionResult(status="ok", action_type=action_type, metadata=metadata)


# ---------------------------------------------------------------------------
# Unavailable fallback
# ---------------------------------------------------------------------------


class UnavailableWarmupTdlibAdapter:
    """Adapter-заглушка, когда live-каналы заглушены конфигом."""

    provider_name = "unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def is_available(self) -> bool:
        return False

    def supports_action(self, action_type: str) -> bool:  # noqa: ARG002
        return False

    def close(self) -> None:
        return None

    def execute_action(
        self, *, account_id: str, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        del account_id, context
        return WarmupActionResult(
            status="unavailable",
            action_type=action_type,
            error_code="warmup_adapter_unavailable",
            error_class="configuration",
            metadata={"reason": self._reason},
        )


# ---------------------------------------------------------------------------
# Real implementation (Phase 3+4 wired TDLib calls)
# ---------------------------------------------------------------------------


_FLOOD_WAIT_RE = re.compile(r"FLOOD_WAIT_(\d+)", re.IGNORECASE)


def _classify_tdlib_error(error: dict[str, Any], action_type: str) -> WarmupActionResult:
    """Перевод TDLib `error` объекта в WarmupActionResult.

    Семантика:
    - FLOOD_WAIT_X → flood_wait + retry_after_seconds.
    - FROZEN/SCAM/account нелигитимен → runtime_broken (диспетчер ставит
      сессию на PAUSED_RISK через circuit breaker, а apply-сторона должна
      отдельно остановить аккаунт через `account_lifecycle`).
    - Прочие 400/500 — network_error.
    """
    message = str(error.get("message") or "TDLib error")
    upper = message.upper()
    flood_match = _FLOOD_WAIT_RE.search(upper)
    if flood_match:
        retry_after = int(flood_match.group(1))
        return WarmupActionResult(
            status="flood_wait",
            action_type=action_type,
            retry_after_seconds=retry_after,
            error_code="tdlib_flood_wait",
            error_class="rate_limit",
            metadata={"message": message, "retry_after_seconds": retry_after},
        )
    if any(token in upper for token in ("FROZEN", "DEACTIVATED", "AUTH_KEY", "USER_DEACTIVATED")):
        # delegate richer mapping to existing helper for consistency with auth
        mapped = map_tdlib_error(error)
        return WarmupActionResult(
            status="runtime_broken",
            action_type=action_type,
            error_code=mapped.recovery_marker or "tdlib_runtime_broken",
            error_class="runtime",
            metadata={"message": message, "runtime_health": mapped.runtime_health},
        )
    return WarmupActionResult(
        status="network_error",
        action_type=action_type,
        error_code="tdlib_error",
        error_class="network",
        metadata={"message": message},
    )


class RealWarmupTdlibAdapter:
    """Боевой адаптер. Использует существующий `RealTdJsonClientFactory`.

    Дизайн:
    - Per-account TDLib client кэшируется внутри адаптера на время жизни
      экземпляра (= один dispatch tick). `close()` корректно закрывает
      все созданные клиенты.
    - Перед action'ом адаптер ждёт `authorizationStateReady`. Если для
      аккаунта нет валидной сессии — возвращаем `runtime_broken` без
      каких-либо TDLib-write-запросов.
    - Все TDLib-команды строятся через `client.send_query` с таймаутом
      из конфига; ошибки мапятся через `_classify_tdlib_error`.
    - Адаптер не пишет в БД и не модифицирует чужой state — диспетчер
      сам обновит counters/events.
    """

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

    # -- adapter contract ----------------------------------------------------

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
        try:
            if action_type == "get_me":
                return self._action_get_me(client, action_type)
            if action_type == "ping_proxy":
                return self._action_ping_proxy(action_type, context)
            if action_type == "feed_read":
                return self._action_feed_read(client, action_type)
            if action_type == "join_chat":
                return self._action_join_chat(client, action_type, context)
            if action_type == "p2p_send":
                return self._action_p2p_send(client, action_type, context)
            return WarmupActionResult(
                status="unsupported",
                action_type=action_type,
                error_code="action_not_supported_in_passive",
                error_class="contract",
            )
        except Exception as exc:
            # последний рубеж защиты — мы не хотим, чтобы TDLib-исключение
            # роняло worker. Отдаём как network_error, чтобы circuit-breaker
            # увидел провал.
            return WarmupActionResult(
                status="network_error",
                action_type=action_type,
                error_code="adapter_raised",
                error_class=exc.__class__.__name__,
                metadata={"message": str(exc)[:200]},
            )

    # -- client lifecycle ----------------------------------------------------

    def _ensure_ready_client(self, account_id: str) -> TdlibClient:
        cached = self._clients.get(account_id)
        if cached is not None:
            return cached
        client = self._client_factory.create(account_id)
        self._clients[account_id] = client
        proxy_applied = False
        # auth state machine — read-only, как в TdlibReadOnlyValidityAdapter,
        # но без отправки кодов/паролей. Если аккаунт требует reauth —
        # диспетчер не должен слать TDLib-команды.
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
                    apply_account_proxy_to_tdlib(client, account_id, config=self._config)
                    proxy_applied = True
                continue
            if mapped.status == TdlibAuthStatus.READY:
                return client
            # Любой другой статус — авторизация не готова: запрещено делать
            # TDLib-вызовы, тем более write.
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

    # -- TDLib actions -------------------------------------------------------

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
        # ensure_ready_client уже подтвердил auth+proxy → факт reachability
        # эквивалентен READY. Не делаем дополнительных TDLib-вызовов.
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
                # одна ошибка не валит весь action — продолжаем. Но если
                # это flood — поднимаемся наверх.
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


class _AdapterClientError(Exception):
    """Внутренняя ошибка инициализации TDLib-клиента в адаптере.

    Не утекает наружу: `RealWarmupTdlibAdapter.execute_action` ловит её и
    конвертирует в `WarmupActionResult`.
    """

    def __init__(
        self,
        *,
        status: str,
        error_code: str,
        error_class: str,
        message: str,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.error_class = error_class
        self.message = message

    def as_action_result(self, action_type: str) -> WarmupActionResult:
        return WarmupActionResult(
            status=self.status,
            action_type=action_type,
            error_code=self.error_code,
            error_class=self.error_class,
            metadata={"message": self.message},
        )

    @classmethod
    def from_tdlib_error(cls, event: dict[str, Any]) -> "_AdapterClientError":
        message = str(event.get("message") or "tdlib error")
        upper = message.upper()
        if "FLOOD" in upper:
            return cls(
                status="flood_wait",
                error_code="tdlib_flood_wait",
                error_class="rate_limit",
                message=message,
            )
        return cls(
            status="runtime_broken",
            error_code="tdlib_auth_error",
            error_class="auth_state",
            message=message,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_warmup_tdlib_adapter(config: Settings = settings) -> WarmupTdlibAdapter:
    """Factory.

    Адаптер активен, если включён хотя бы один live-уровень
    (`warmup_passive_enabled`/`warmup_network_enabled`/`warmup_advanced_enabled`).
    Поддерживаемые action'ы вычисляются строго по самому высокому из включённых
    уровней.

    Если ни один уровень не включён — возвращаем `UnavailableWarmupTdlibAdapter`,
    диспетчер запишет `task_skipped reason="passive_disabled"`.
    """
    active_modes: list[str] = []
    if config.warmup_passive_enabled:
        active_modes.append("passive")
    if config.warmup_network_enabled:
        active_modes.append("network")
    if config.warmup_advanced_enabled:
        active_modes.append("advanced")
    if not active_modes:
        return UnavailableWarmupTdlibAdapter("warmup_live_levels_all_disabled")
    try:
        factory: TdlibClientFactory = RealTdJsonClientFactory(config.tdlib_shared_library_path)
    except OSError as exc:
        return UnavailableWarmupTdlibAdapter(f"tdlib_load_failed: {exc}")
    return RealWarmupTdlibAdapter(
        client_factory=factory,
        config=config,
        supported_modes=tuple(active_modes),
    )
