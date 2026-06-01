from __future__ import annotations

# pyright: reportUnusedFunction=false

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    utc_now,
)
from app.modules.account_safety.interfaces import (
    SafetyGateVerdict,
    evaluate as evaluate_safety_gate,
)
from app.modules.human_behavior.interfaces import DecoyAction, TypingFragment
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.errors import NeuroConflictError


@dataclass(frozen=True)
class PreparedSend:
    allowed: bool
    reason: str | None = None


@dataclass(frozen=True)
class SentCommentResult:
    telegram_message_id: str
    sent_at: datetime


@dataclass(frozen=True)
class _SendContext:
    attempt: NeuroCommentAttempt
    campaign: NeuroCommentCampaign
    comment: NeuroCommentGeneratedComment
    observed_post: NeuroCommentObservedPost | None
    target: NeuroCommentTarget | None
    campaign_account: NeuroCommentCampaignAccount | None


def _discussion_chat_id(context: _SendContext) -> str:
    assert context.target is not None
    assert context.observed_post is not None
    discussion_chat_id = (
        context.observed_post.discussion_chat_id or context.target.discussion_chat_id
    )
    if not discussion_chat_id:
        raise NeuroConflictError("target has no discussion", error_code="TARGET_NO_DISCUSSION")
    return str(discussion_chat_id)


def _comment_text(context: _SendContext) -> str:
    return (
        context.comment.final_text or context.comment.edited_text or context.comment.generated_text
    )


@dataclass(frozen=True)
class BehaviorEmulatorSendPlan:
    typing_fragments: tuple[TypingFragment, ...]
    decoy_actions: tuple[DecoyAction, ...]
    typing_duration_seconds: float


class TelegramCommentSendError(RuntimeError):
    def __init__(
        self,
        error_code: str,
        message: str | None = None,
        *,
        flood_wait_seconds: int | None = None,
    ) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code
        self.flood_wait_seconds = flood_wait_seconds


class TelegramCommentSender(Protocol):
    def send_comment(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        text: str,
        random_id: int | None = None,
    ) -> SentCommentResult: ...


class BehaviorEmulatorBeforeSendHook(Protocol):
    def before_send(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        plan: BehaviorEmulatorSendPlan,
    ) -> None: ...


class NoopBehaviorEmulatorBeforeSendHook:
    def before_send(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        plan: BehaviorEmulatorSendPlan,
    ) -> None:
        _ = (account_id, discussion_chat_id, reply_to_message_id, plan)


class FakeTelegramCommentSender:
    def __init__(
        self,
        *,
        telegram_message_id: str = "fake-telegram-message",
        error: TelegramCommentSendError | None = None,
    ) -> None:
        self._telegram_message_id = telegram_message_id
        self._error = error
        self.calls = 0
        self.last_discussion_chat_id: str | None = None
        self.last_reply_to_message_id: str | None = None
        self.last_random_id: int | None = None

    def send_comment(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        text: str,
        random_id: int | None = None,
    ) -> SentCommentResult:
        _ = (account_id, text)
        self.calls += 1
        self.last_discussion_chat_id = discussion_chat_id
        self.last_reply_to_message_id = reply_to_message_id
        self.last_random_id = random_id
        if self._error is not None:
            raise self._error
        return SentCommentResult(
            telegram_message_id=self._telegram_message_id,
            sent_at=utc_now(),
        )


def build_telegram_comment_sender(config: Settings = settings) -> TelegramCommentSender:
    if not config.neuro_comment_tdlib_send_enabled:
        return FakeTelegramCommentSender()
    from app.modules.neuro_commenting.tdlib_comment_sender import TdlibTelegramCommentSender

    return TdlibTelegramCommentSender(config=config)


def _target_or_none(
    session: Session, target_id: str | None, campaign_id: str
) -> NeuroCommentTarget | None:
    if target_id is None:
        return None
    return repository.get_target(session, target_id=target_id, campaign_id=campaign_id)


def _campaign_account_or_none(
    session: Session, campaign_id: str, account_id: str | None
) -> NeuroCommentCampaignAccount | None:
    if account_id is None:
        return None
    return repository.get_campaign_account(session, campaign_id=campaign_id, account_id=account_id)


def _evaluate_commenting_gate(
    session: Session, *, workspace_id: str, context: _SendContext
) -> SafetyGateVerdict | None:
    account_id = context.attempt.account_id or context.comment.account_id
    if account_id is None:
        return None
    return evaluate_safety_gate(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        intent="commenting",
    )
