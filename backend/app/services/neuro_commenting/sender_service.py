from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
)
from app.services.neuro_commenting import repository
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.enums import (
    NeuroAttemptStatus,
    NeuroCampaignAccountStatus,
    NeuroCampaignStatus,
    NeuroEventLevel,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    NeuroTargetStatus,
)
from app.services.neuro_commenting.errors import (
    NeuroConflictError,
    NeuroRateLimiterNotReadyError,
    NeuroRuntimeDisabledError,
    NeuroValidationError,
)


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
    ) -> SentCommentResult: ...


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
        self.last_reply_to_message_id: str | None = None

    def send_comment(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        text: str,
    ) -> SentCommentResult:
        _ = (account_id, discussion_chat_id, text)
        self.calls += 1
        self.last_reply_to_message_id = reply_to_message_id
        if self._error is not None:
            raise self._error
        return SentCommentResult(
            telegram_message_id=self._telegram_message_id,
            sent_at=datetime.now(UTC),
        )


class SenderService:
    def __init__(
        self,
        *,
        config: Settings = settings,
        sender: TelegramCommentSender | None = None,
        analytics: AnalyticsService | None = None,
    ) -> None:
        self._config = config
        self._sender = sender
        self._analytics = analytics or AnalyticsService()

    def prepare_send(
        self, *, campaign: NeuroCommentCampaign, comment: NeuroCommentGeneratedComment
    ) -> PreparedSend:
        if campaign.dry_run or not campaign.auto_send_enabled:
            return PreparedSend(allowed=False, reason="auto_send_disabled")
        if comment.approval_status != NeuroGeneratedApprovalStatus.APPROVED.value:
            return PreparedSend(allowed=False, reason="not_approved")
        if comment.safety_status == NeuroSafetyStatus.BLOCKED.value:
            return PreparedSend(allowed=False, reason="safety_blocked")
        return PreparedSend(allowed=True)

    def send_attempt(
        self, session: Session, *, attempt_id: str, workspace_id: str
    ) -> NeuroCommentAttempt:
        context = self._load_context(session, attempt_id=attempt_id, workspace_id=workspace_id)
        attempt = context.attempt
        if attempt.status == NeuroAttemptStatus.SENT.value and attempt.telegram_message_id:
            return attempt
        self._validate_context(context)
        if not self._config.neuro_comment_tdlib_send_enabled:
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=attempt.account_id,
                target_id=attempt.target_id,
                generated_comment_id=context.comment.id,
                attempt_id=attempt.id,
                event_type="manual_send_blocked",
                message="TDLib neuro-comment sending is disabled.",
                data={"error_code": "NEURO_COMMENT_SEND_DISABLED"},
            )
            raise NeuroRuntimeDisabledError(
                "TDLib neuro-comment sending is disabled.",
                error_code="NEURO_COMMENT_SEND_DISABLED",
            )
        if self._config.neuro_comment_require_redis_limiter_for_send:
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=attempt.account_id,
                target_id=attempt.target_id,
                generated_comment_id=context.comment.id,
                attempt_id=attempt.id,
                event_type="manual_send_blocked",
                message="Neuro-comment sending requires Redis limiter.",
                data={"error_code": "NEURO_COMMENT_RATE_LIMITER_NOT_READY"},
            )
            raise NeuroRateLimiterNotReadyError()
        assert context.target is not None
        final_text = (
            context.comment.final_text
            or context.comment.edited_text
            or context.comment.generated_text
        )
        attempt.status = NeuroAttemptStatus.SENDING.value
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=attempt.account_id,
            target_id=attempt.target_id,
            observed_post_id=attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=attempt.id,
            event_type="comment_send_started",
            message="manual neuro-comment send started",
            data={},
        )
        try:
            result = self._comment_sender().send_comment(
                account_id=str(attempt.account_id),
                discussion_chat_id=str(context.target.discussion_chat_id),
                reply_to_message_id=str(
                    context.observed_post.source_message_id
                    if context.observed_post is not None
                    else ""
                ),
                text=final_text,
            )
        except TelegramCommentSendError as exc:
            self._mark_send_error(session, workspace_id=workspace_id, attempt=attempt, error=exc)
            return attempt
        attempt.status = NeuroAttemptStatus.SENT.value
        attempt.telegram_message_id = result.telegram_message_id
        attempt.sent_at = result.sent_at
        attempt.error_code = None
        attempt.error_message = None
        if context.campaign_account is not None:
            context.campaign_account.comments_sent += 1
            context.campaign_account.last_used_at = result.sent_at
        context.target.success_count += 1
        context.target.last_commented_at = result.sent_at
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=attempt.account_id,
            target_id=attempt.target_id,
            observed_post_id=attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=attempt.id,
            event_type="comment_sent",
            message="manual neuro-comment sent",
            data={"attempt_id": attempt.id},
        )
        return attempt

    def preflight_attempt(
        self, session: Session, *, attempt_id: str, workspace_id: str
    ) -> NeuroCommentAttempt:
        context = self._load_context(session, attempt_id=attempt_id, workspace_id=workspace_id)
        if (
            context.attempt.status == NeuroAttemptStatus.SENT.value
            and context.attempt.telegram_message_id
        ):
            return context.attempt
        self._validate_context(context)
        return context.attempt

    def _load_context(
        self, session: Session, *, attempt_id: str, workspace_id: str
    ) -> _SendContext:
        attempt = repository.require_attempt_for_workspace(
            session, attempt_id=attempt_id, workspace_id=workspace_id
        )
        campaign = repository.require_campaign(
            session, campaign_id=attempt.campaign_id, workspace_id=workspace_id
        )
        comment = repository.require_generated_comment(
            session, comment_id=attempt.generated_comment_id, workspace_id=workspace_id
        )
        observed_post = (
            repository.get_observed_post(
                session,
                observed_post_id=attempt.observed_post_id,
                campaign_id=campaign.id,
            )
            if attempt.observed_post_id is not None
            else None
        )
        target = _target_or_none(session, attempt.target_id, campaign.id)
        campaign_account = _campaign_account_or_none(session, campaign.id, attempt.account_id)
        return _SendContext(
            attempt=attempt,
            campaign=campaign,
            comment=comment,
            observed_post=observed_post,
            target=target,
            campaign_account=campaign_account,
        )

    def _validate_context(self, context: _SendContext) -> None:
        self._validate_send(
            context.campaign,
            context.comment,
            context.target,
            context.campaign_account,
        )

    def _comment_sender(self) -> TelegramCommentSender:
        if self._sender is None:
            self._sender = build_telegram_comment_sender(self._config)
        return self._sender

    def _validate_send(
        self,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        target: NeuroCommentTarget | None,
        campaign_account: NeuroCommentCampaignAccount | None,
    ) -> None:
        if campaign.status != NeuroCampaignStatus.RUNNING.value:
            raise NeuroConflictError("campaign is not running", error_code="CAMPAIGN_NOT_RUNNING")
        if campaign.dry_run:
            raise NeuroConflictError("dry-run campaign cannot send", error_code="CAMPAIGN_DRY_RUN")
        if comment.approval_status != NeuroGeneratedApprovalStatus.APPROVED.value:
            raise NeuroValidationError("comment is not approved", error_code="COMMENT_NOT_APPROVED")
        if comment.safety_status == NeuroSafetyStatus.BLOCKED.value:
            raise NeuroValidationError("blocked comment cannot send", error_code="COMMENT_BLOCKED")
        if not comment.final_text:
            raise NeuroValidationError(
                "comment final text is required", error_code="COMMENT_TEXT_MISSING"
            )
        if target is None or not target.discussion_chat_id:
            raise NeuroConflictError("target has no discussion", error_code="TARGET_NO_DISCUSSION")
        if target.status != NeuroTargetStatus.ACTIVE.value:
            raise NeuroConflictError("target is not active", error_code="TARGET_NOT_ACTIVE")
        if (
            campaign_account is None
            or campaign_account.status != NeuroCampaignAccountStatus.ACTIVE.value
        ):
            raise NeuroConflictError("account is not active", error_code="ACCOUNT_NOT_ACTIVE")

    def _mark_send_error(
        self,
        session: Session,
        *,
        workspace_id: str,
        attempt: NeuroCommentAttempt,
        error: TelegramCommentSendError,
    ) -> None:
        now = datetime.now(UTC)
        attempt.error_code = error.error_code
        attempt.error_message = str(error)[:300]
        attempt.failed_at = now
        event_type = "comment_send_failed"
        if error.error_code == "FLOOD_WAIT":
            attempt.status = NeuroAttemptStatus.FLOOD_WAIT.value
            attempt.flood_wait_seconds = error.flood_wait_seconds
            event_type = "comment_flood_wait"
            campaign_account = _campaign_account_or_none(
                session, attempt.campaign_id, attempt.account_id
            )
            if campaign_account is not None and error.flood_wait_seconds is not None:
                campaign_account.cooldown_until = now + timedelta(seconds=error.flood_wait_seconds)
        else:
            attempt.status = NeuroAttemptStatus.FAILED.value
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=attempt.campaign_id,
            account_id=attempt.account_id,
            target_id=attempt.target_id,
            observed_post_id=attempt.observed_post_id,
            generated_comment_id=attempt.generated_comment_id,
            attempt_id=attempt.id,
            event_type=event_type,
            event_level=NeuroEventLevel.WARNING,
            message="manual neuro-comment send failed",
            data={"error_code": error.error_code},
        )


def build_telegram_comment_sender(config: Settings = settings) -> TelegramCommentSender:
    if not config.neuro_comment_tdlib_send_enabled:
        return FakeTelegramCommentSender()
    from app.services.neuro_commenting.tdlib_comment_sender import TdlibTelegramCommentSender

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
