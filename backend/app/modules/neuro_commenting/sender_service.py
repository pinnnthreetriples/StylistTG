from __future__ import annotations

from typing import Any

from app.config import Settings, settings
from app.modules.account_safety.interfaces import SafetyGateReservation
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.sender_contracts import (
    BehaviorEmulatorBeforeSendHook,
    BehaviorEmulatorSendPlan,
    FakeTelegramCommentSender,
    NoopBehaviorEmulatorBeforeSendHook,
    PreparedSend,
    SentCommentResult,
    TelegramCommentSendError,
    TelegramCommentSender,
    build_telegram_comment_sender,
)
from app.modules.neuro_commenting.sender_flow import SenderFlowMixin
from app.modules.neuro_commenting.sender_preflight import SenderPreflightMixin
from app.modules.neuro_commenting.sender_reservations import SenderReservationMixin
from app.modules.neuro_commenting.sender_results import SenderResultsMixin


class SenderService(
    SenderFlowMixin,
    SenderPreflightMixin,
    SenderReservationMixin,
    SenderResultsMixin,
):
    def __init__(
        self,
        *,
        config: Settings = settings,
        sender: TelegramCommentSender | None = None,
        analytics: AnalyticsService | None = None,
        limiter: Any | None = None,
        redis_client: Any | None = None,
        behavior_emulator_hook: BehaviorEmulatorBeforeSendHook | None = None,
    ) -> None:
        self._config = config
        self._sender = sender
        self._analytics = analytics or AnalyticsService()
        self._limiter = limiter
        self._redis_client = redis_client
        self._behavior_emulator_hook = (
            behavior_emulator_hook or NoopBehaviorEmulatorBeforeSendHook()
        )
        self._gate_reservation: SafetyGateReservation | None = None


__all__ = [
    "BehaviorEmulatorBeforeSendHook",
    "BehaviorEmulatorSendPlan",
    "FakeTelegramCommentSender",
    "NoopBehaviorEmulatorBeforeSendHook",
    "PreparedSend",
    "SenderService",
    "SentCommentResult",
    "TelegramCommentSendError",
    "TelegramCommentSender",
    "build_telegram_comment_sender",
]
