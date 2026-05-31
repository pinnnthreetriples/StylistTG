from __future__ import annotations

import random
from typing import Any

from app.adapters.warmup_tdlib_contracts import WarmupActionResult, collect_supported_actions


class MockWarmupTdlibAdapter:
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

    def close(self) -> None:
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
            return self._join_chat_result(action_type, context)
        if action_type == "p2p_send":
            return self._p2p_send_result(action_type, context)
        return self._read_only_result(action_type, context)

    def _join_chat_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
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

    def _p2p_send_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
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

    def _read_only_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
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


class UnavailableWarmupTdlibAdapter:
    provider_name = "unavailable"

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def is_available(self) -> bool:
        return False

    def supports_action(self, action_type: str) -> bool:
        del action_type
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
