from __future__ import annotations

# pyright: reportPrivateUsage=false

from app.modules.neuro_commenting.sender_runtime import (
    BehaviorEmulatorBeforeSendHook,
    BehaviorEmulatorSendPlan,
    FakeTelegramCommentSender,
    NoopBehaviorEmulatorBeforeSendHook,
    PreparedSend,
    SentCommentResult,
    TelegramCommentSendError,
    TelegramCommentSender,
    _SendContext,
    _campaign_account_or_none,
    _comment_text,
    _discussion_chat_id,
    _evaluate_commenting_gate,
    _target_or_none,
    build_telegram_comment_sender,
)

__all__ = [
    "BehaviorEmulatorBeforeSendHook",
    "BehaviorEmulatorSendPlan",
    "FakeTelegramCommentSender",
    "NoopBehaviorEmulatorBeforeSendHook",
    "PreparedSend",
    "SentCommentResult",
    "TelegramCommentSendError",
    "TelegramCommentSender",
    "_SendContext",
    "_campaign_account_or_none",
    "_comment_text",
    "_discussion_chat_id",
    "_evaluate_commenting_gate",
    "_target_or_none",
    "build_telegram_comment_sender",
]
