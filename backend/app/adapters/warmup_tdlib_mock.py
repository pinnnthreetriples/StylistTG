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
        if action_type == "channel_browse":
            return self._channel_browse_result(action_type, context)
        if action_type == "scroll_channels":
            return self._scroll_channels_result(action_type, context)
        if action_type == "view_dialogs":
            return self._view_dialogs_result(action_type, context)
        if action_type == "mark_as_read":
            return self._mark_as_read_result(action_type, context)
        if action_type == "search_messages":
            return self._search_messages_result(action_type, context)
        if action_type == "vote_poll":
            return self._vote_poll_result(action_type, context)
        if action_type == "watch_video":
            return self._watch_video_result(action_type, context)
        if action_type == "listen_voice":
            return self._listen_voice_result(action_type, context)
        if action_type == "view_story":
            return self._view_story_result(action_type, context)
        if action_type == "react_to_post":
            return self._react_to_post_result(action_type, context)
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

    def _channel_browse_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="channel_browse_missing_channel",
                error_class="contract",
            )
        messages_total = self._rng.randint(8, 24)
        messages_viewed = self._rng.randint(1, messages_total)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(80, 260),
                "channel_ref": channel_ref,
                "chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                "messages_total": messages_total,
                "messages_viewed": messages_viewed,
                "scroll_depth": round(messages_viewed / messages_total, 2),
            },
        )

    def _view_story_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="view_story_missing_channel",
                error_class="contract",
            )
        has_stories = bool(context.get("has_stories", True))
        viewed_count = self._rng.randint(1, 3) if has_stories else 0
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(60, 220),
                "channel_ref": channel_ref,
                "has_stories": has_stories,
                "viewed_count": viewed_count,
            },
        )

    def _scroll_channels_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="scroll_channels_missing_channel",
                error_class="contract",
            )
        history_limit = int(context.get("history_limit") or 30)
        messages_total = self._rng.randint(20, max(20, history_limit))
        messages_viewed = self._rng.randint(5, messages_total)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(140, 420),
                "channel_ref": channel_ref,
                "chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                "messages_total": messages_total,
                "messages_viewed": messages_viewed,
                "scroll_depth": round(messages_viewed / messages_total, 2),
            },
        )

    def _view_dialogs_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        del context
        chats_seen = self._rng.randint(3, 5)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(70, 220),
                "chats_seen": chats_seen,
                "messages_viewed": self._rng.randint(1, chats_seen),
            },
        )

    def _mark_as_read_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        del context
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(60, 200),
                "chats_marked": self._rng.randint(3, 8),
            },
        )

    def _search_messages_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        query = str(context.get("search_query") or "")
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(80, 240),
                "query": query,
                "results_seen": self._rng.randint(0, 10),
            },
        )

    def _vote_poll_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="vote_poll_missing_channel",
                error_class="contract",
            )
        if context.get("has_open_poll") is False:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="no_open_poll_found",
                error_class="content",
                metadata={"provider": self.provider_name, "channel_ref": channel_ref},
            )
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(90, 240),
                "channel_ref": channel_ref,
                "chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                "message_id": self._rng.randint(1, 1_000_000),
                "chosen_option": str(self._rng.randint(0, 3)),
                "safety_hint": context.get("safety_hint") or "avoid_empty_or_new_accounts",
            },
        )

    def _watch_video_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        return self._media_activity_result(
            action_type,
            context,
            missing_error="watch_video_missing_channel",
            content_flag="has_video",
            skip_error="no_video_found",
        )

    def _listen_voice_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        return self._media_activity_result(
            action_type,
            context,
            missing_error="listen_voice_missing_channel",
            content_flag="has_voice",
            skip_error="no_voice_found",
        )

    def _media_activity_result(
        self,
        action_type: str,
        context: dict[str, Any],
        *,
        missing_error: str,
        content_flag: str,
        skip_error: str,
    ) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code=missing_error,
                error_class="contract",
            )
        if context.get(content_flag) is False:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code=skip_error,
                error_class="content",
                metadata={
                    "provider": self.provider_name,
                    "channel_ref": channel_ref,
                    "traffic_heavy": True,
                },
            )
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(180, 520),
                "channel_ref": channel_ref,
                "chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                "message_id": self._rng.randint(1, 1_000_000),
                "file_id": self._rng.randint(1_000, 99_999),
                "traffic_heavy": True,
            },
        )

    def _react_to_post_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        reactions = list(context.get("available_reactions") or ())
        if not channel_ref or not reactions:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="react_to_post_missing_context",
                error_class="contract",
            )
        reaction = reactions[self._rng.randint(0, len(reactions) - 1)]
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(90, 240),
                "channel_ref": channel_ref,
                "chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                "message_id": self._rng.randint(1, 1_000_000),
                "reaction": reaction,
                "has_reactions": True,
                "available_reactions": reactions,
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
