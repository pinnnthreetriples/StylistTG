from __future__ import annotations

# pyright: reportUnknownVariableType=false

import random
from typing import Any, cast

from app.adapters.warmup_tdlib_contracts import WarmupActionResult, collect_supported_actions
from app.modules.warmup.typing import compute_typing_duration


def _is_protected_chat_id(chat_id: int) -> bool:
    return chat_id >= 0 or chat_id == 777000


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
        if action_type == "search_gif":
            return self._search_gif_result(action_type, context)
        if action_type == "view_stickers":
            return self._view_stickers_result(action_type, context)
        if action_type == "inline_bot":
            return self._inline_bot_result(action_type, context)
        if action_type == "link_preview":
            return self._link_preview_result(action_type, context)
        if action_type == "forward_message":
            return self._forward_message_result(action_type, context)
        if action_type == "saved_messages":
            return self._saved_messages_result(action_type, context)
        if action_type == "sync_contacts":
            return self._sync_contacts_result(action_type, context)
        if action_type == "archive_chat":
            return self._archive_chat_result(action_type, context)
        if action_type == "mute_chat":
            return self._mute_chat_result(action_type, context)
        if action_type in {
            "simulate_typing",
            "view_profile",
            "check_settings",
            "emoji_status",
            "drafts",
            "scheduled_messages",
            "update_profile_gradual",
            "notification_settings",
        }:
            return self._profile_settings_result(action_type, context)
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

    def _search_gif_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(180, 520),
                "query": str(context.get("search_query") or "cat"),
                "animations_seen": self._rng.randint(1, 10),
                "files_touched": self._rng.randint(1, 3),
                "traffic_heavy": True,
            },
        )

    def _view_stickers_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        del context
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(120, 340),
                "stickers_seen": self._rng.randint(1, 8),
                "sets_viewed": self._rng.randint(1, 3),
                "traffic_heavy": True,
            },
        )

    def _inline_bot_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        bot_username = str(context.get("inline_bot_username") or "@gif")
        if bot_username not in {"@gif", "@pic", "@sticker", "@vid"}:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="inline_bot_not_approved",
                error_class="safety",
                metadata={"provider": self.provider_name, "traffic_heavy": True},
            )
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(100, 300),
                "bot_username": bot_username,
                "query": str(context.get("inline_query") or "cat"),
                "results_seen": self._rng.randint(0, 20),
                "traffic_heavy": True,
            },
        )

    def _link_preview_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(80, 240),
                "preview_url": str(context.get("preview_url") or "https://example.com/"),
                "traffic_heavy": True,
            },
        )

    def _forward_message_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        channel_ref = context.get("channel_ref")
        if not channel_ref:
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="forward_message_missing_channel",
                error_class="contract",
            )
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(90, 240),
                "channel_ref": channel_ref,
                "from_chat_id": -100_000_000_000 - self._rng.randint(1, 10_000),
                "to_chat": "saved_messages",
                "message_id": self._rng.randint(1, 1_000_000),
            },
        )

    def _saved_messages_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        text = str(context.get("note_text") or "remember")
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(70, 180),
                "to_chat": "saved_messages",
                "text_length": len(text),
            },
        )

    def _sync_contacts_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        contacts_pool = list(context.get("contacts_pool") or [])
        if not contacts_pool:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="no_contacts_pool_available",
                error_class="content",
                metadata={"provider": self.provider_name},
            )
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(120, 260),
                "contacts_read": self._rng.randint(0, 20),
                "contacts_imported": len(contacts_pool),
            },
        )

    def _archive_chat_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        chat_id = int(context.get("chat_id") or (-100_000_000_000 - self._rng.randint(1, 10_000)))
        if _is_protected_chat_id(chat_id):
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="protected_chat",
                error_class="safety",
                metadata={"provider": self.provider_name, "chat_id": chat_id},
            )
        temporary = bool(context.get("temporary", False))
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(80, 180),
                "chat_id": chat_id,
                "archived": True,
                "temporary": temporary,
                "reversed": temporary,
            },
        )

    def _mute_chat_result(self, action_type: str, context: dict[str, Any]) -> WarmupActionResult:
        chat_id = int(context.get("chat_id") or (-100_000_000_000 - self._rng.randint(1, 10_000)))
        if _is_protected_chat_id(chat_id):
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="protected_chat",
                error_class="safety",
                metadata={"provider": self.provider_name, "chat_id": chat_id},
            )
        temporary = bool(context.get("temporary", False))
        mute_for_seconds = int(context.get("mute_for_seconds") or 86_400)
        return WarmupActionResult(
            status="ok",
            action_type=action_type,
            metadata={
                "provider": self.provider_name,
                "latency_ms": self._rng.randint(80, 180),
                "chat_id": chat_id,
                "mute_for_seconds": mute_for_seconds,
                "temporary": temporary,
                "reversed": temporary,
            },
        )

    def _profile_settings_result(
        self, action_type: str, context: dict[str, Any]
    ) -> WarmupActionResult:
        if action_type in {"simulate_typing", "drafts"} and not (
            context.get("chat_id") or context.get("channel_ref")
        ):
            return WarmupActionResult(
                status="missing_context",
                action_type=action_type,
                error_code="profile_action_missing_chat",
                error_class="contract",
            )
        if action_type == "emoji_status" and context.get("is_premium") is False:
            return WarmupActionResult(
                status="skipped",
                action_type=action_type,
                error_code="non_premium_account",
                error_class="capability",
            )
        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "latency_ms": self._rng.randint(50, 180),
        }
        if action_type == "simulate_typing":
            metadata["typing_duration_seconds"] = int(
                context.get("typing_duration_seconds") or self._rng.randint(3, 8)
            )
        elif action_type == "view_profile":
            metadata["user_id"] = int(context.get("user_id") or self._rng.randint(1, 999_999))
        elif action_type == "check_settings":
            metadata["option_name"] = str(
                context.get("option_name") or "notification_group_count_max"
            )
        elif action_type == "emoji_status":
            metadata["emoji_id"] = str(context.get("emoji_id") or "🙂")
        elif action_type == "drafts":
            metadata["draft_length"] = len(str(context.get("draft_text") or "todo"))
            metadata["temporary"] = bool(context.get("temporary", True))
            metadata["cleared"] = metadata["temporary"]
        elif action_type == "scheduled_messages":
            metadata["to_chat"] = "saved_messages"
            metadata["scheduled"] = True
            metadata["temporary"] = bool(context.get("temporary", True))
            metadata["rescheduled"] = metadata["temporary"]
        elif action_type == "update_profile_gradual":
            metadata["profile_field"] = str(context.get("profile_field") or "bio")
        elif action_type == "notification_settings":
            metadata["notification_scope"] = str(context.get("notification_scope") or "private")
            metadata["mute_for_seconds"] = int(context.get("mute_for_seconds") or 0)
        return WarmupActionResult(status="ok", action_type=action_type, metadata=metadata)

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
                "typing_started": True,
                "typing_duration_ms": int(
                    compute_typing_duration(
                        len(text),
                        personality_seed=_personality_seed(context),
                        rng=self._rng,
                    )
                    * 1000
                ),
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


def _personality_seed(context: dict[str, Any]) -> dict[str, Any]:
    raw = context.get("personality_seed")
    return cast(dict[str, Any], raw) if isinstance(raw, dict) else {}
