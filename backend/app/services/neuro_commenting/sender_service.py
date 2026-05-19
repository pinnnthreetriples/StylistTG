from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session, object_session

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
from app.services.neuro_commenting.account_health_service import AccountHealthService
from app.services.neuro_commenting.account_selector import DefaultAccountReadinessProvider
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
    NeuroRuntimeDisabledError,
    NeuroValidationError,
)
from app.services.neuro_commenting.limits_service import LimitsService
from app.services.neuro_commenting.rate_limiter import (
    NeuroCommentRateLimiter,
    RateLimitReservation,
    RateLimitScope,
)
from app.services.neuro_commenting.rules_policy import ChannelRulesPolicy
from app.services.neuro_commenting.target_health_service import TargetHealthService


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
        self.last_discussion_chat_id: str | None = None
        self.last_reply_to_message_id: str | None = None

    def send_comment(
        self,
        *,
        account_id: str,
        discussion_chat_id: str,
        reply_to_message_id: str,
        text: str,
    ) -> SentCommentResult:
        _ = (account_id, text)
        self.calls += 1
        self.last_discussion_chat_id = discussion_chat_id
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
        limiter: Any | None = None,
        redis_client: Any | None = None,
    ) -> None:
        self._config = config
        self._sender = sender
        self._analytics = analytics or AnalyticsService()
        self._limiter = limiter
        self._redis_client = redis_client

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
        if context.target is not None:
            decision = ChannelRulesPolicy().check_target_allowed(
                session, workspace_id=workspace_id, target=context.target
            )
            if not decision.allowed:
                attempt.status = NeuroAttemptStatus.SKIPPED.value
                attempt.error_code = "CHANNEL_RULE_BLOCKED"
                attempt.error_message = decision.reason
                self._analytics.write_event(
                    session,
                    workspace_id=workspace_id,
                    campaign_id=context.campaign.id,
                    account_id=attempt.account_id,
                    target_id=attempt.target_id,
                    observed_post_id=attempt.observed_post_id,
                    generated_comment_id=context.comment.id,
                    attempt_id=attempt.id,
                    event_type="channel_rule_blocked",
                    event_level=NeuroEventLevel.WARNING,
                    message=decision.reason or "channel rule blocked send",
                    data={"matched_rule_id": decision.matched_rule_id},
                )
                return attempt
        reservation = self._reserve_for_attempt(session, context=context, workspace_id=workspace_id)
        if (
            reservation is None
            and attempt.status == NeuroAttemptStatus.SKIPPED.value
            and attempt.error_code == "RATE_LIMIT_DENIED"
        ):
            return attempt
        assert context.target is not None
        assert context.observed_post is not None
        discussion_chat_id = (
            context.observed_post.discussion_chat_id or context.target.discussion_chat_id
        )
        if not discussion_chat_id:
            raise NeuroConflictError("target has no discussion", error_code="TARGET_NO_DISCUSSION")
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
                discussion_chat_id=str(discussion_chat_id),
                reply_to_message_id=str(context.observed_post.discussion_message_id),
                text=final_text,
            )
        except TelegramCommentSendError as exc:
            self._rollback_reservation(reservation)
            self._mark_send_error(session, workspace_id=workspace_id, attempt=attempt, error=exc)
            return attempt
        self._commit_reservation(reservation)
        attempt.status = NeuroAttemptStatus.SENT.value
        attempt.telegram_message_id = result.telegram_message_id
        attempt.sent_at = result.sent_at
        attempt.error_code = None
        attempt.error_message = None
        self.record_attempt_success(
            session,
            campaign=context.campaign,
            comment=context.comment,
            attempt=attempt,
            telegram_message_id=result.telegram_message_id,
        )
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

    def send_comment(
        self,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
    ) -> NeuroCommentAttempt:
        session = self._session_for(comment, attempt, campaign)
        target = self._target_for_send(session, campaign=campaign, comment=comment, attempt=attempt)
        if session is not None and target is not None:
            decision = ChannelRulesPolicy().check_target_allowed(
                session, workspace_id=campaign.workspace_id, target=target
            )
            if not decision.allowed:
                attempt.status = NeuroAttemptStatus.SKIPPED.value
                attempt.error_code = "CHANNEL_RULE_BLOCKED"
                attempt.error_message = decision.reason
                return attempt

        limiter = self._limiter or self._limiter_for_send(session, campaign)
        reservation = limiter.reserve(
            RateLimitScope(
                workspace_id=campaign.workspace_id,
                campaign_id=campaign.id,
                account_id=attempt.account_id or comment.account_id,
                target_id=attempt.target_id or comment.target_id,
            )
        )
        if not reservation.allowed:
            attempt.status = NeuroAttemptStatus.SKIPPED.value
            attempt.error_code = "RATE_LIMIT_DENIED"
            attempt.error_message = reservation.reason
            return attempt
        attempt.status = NeuroAttemptStatus.SKIPPED.value
        attempt.error_code = "AUTO_SEND_DISABLED"
        attempt.error_message = "TDLib comment sender is not enabled in foundation skeleton"
        limiter.rollback(reservation)
        return attempt

    def record_attempt_success(
        self,
        session: Session,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
        telegram_message_id: str | None = None,
    ) -> NeuroCommentAttempt:
        now = datetime.now(UTC)
        attempt.status = NeuroAttemptStatus.SENT.value
        attempt.telegram_message_id = telegram_message_id or attempt.telegram_message_id
        attempt.sent_at = attempt.sent_at or now
        attempt.error_code = None
        attempt.error_message = None
        account_id = attempt.account_id or comment.account_id
        target_id = attempt.target_id or comment.target_id
        if account_id is not None:
            AccountHealthService().record_account_send_success(
                session,
                campaign_id=campaign.id,
                account_id=account_id,
                workspace_id=campaign.workspace_id,
            )
        if target_id is not None:
            target_health = TargetHealthService()
            target_health.record_target_success(
                session, workspace_id=campaign.workspace_id, target_id=target_id
            )
            target_health.suggest_rules_for_target(
                session, workspace_id=campaign.workspace_id, target_id=target_id
            )
        return attempt

    def record_attempt_failure(
        self,
        session: Session,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
        error_code: str,
        error_message: str | None = None,
        flood_wait_seconds: int | None = None,
    ) -> NeuroCommentAttempt:
        now = datetime.now(UTC)
        attempt.status = NeuroAttemptStatus.FAILED.value
        attempt.error_code = error_code
        attempt.error_message = error_message
        attempt.failed_at = now
        account_id = attempt.account_id or comment.account_id
        target_id = attempt.target_id or comment.target_id
        if error_code == "FLOOD_WAIT":
            seconds = max(1, int(flood_wait_seconds or attempt.flood_wait_seconds or 1))
            attempt.flood_wait_seconds = seconds
            if account_id is not None:
                AccountHealthService().record_account_flood_wait(
                    session,
                    campaign_id=campaign.id,
                    account_id=account_id,
                    workspace_id=campaign.workspace_id,
                    flood_wait_seconds=seconds,
                )
            if target_id is not None:
                target_health = TargetHealthService()
                target_health.record_target_flood_wait(
                    session, workspace_id=campaign.workspace_id, target_id=target_id
                )
                target_health.suggest_rules_for_target(
                    session, workspace_id=campaign.workspace_id, target_id=target_id
                )
            return attempt
        if account_id is not None:
            AccountHealthService().record_account_send_failure(
                session,
                campaign_id=campaign.id,
                account_id=account_id,
                workspace_id=campaign.workspace_id,
                error_code=error_code,
            )
        if target_id is not None:
            target_health = TargetHealthService()
            target_health.record_target_failure(
                session,
                workspace_id=campaign.workspace_id,
                target_id=target_id,
                error_code=error_code,
            )
            target_health.suggest_rules_for_target(
                session, workspace_id=campaign.workspace_id, target_id=target_id
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
        self._validate_preflight_guards(session, workspace_id=workspace_id, context=context)
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
            context.observed_post,
            context.target,
            context.campaign_account,
        )

    def _validate_preflight_guards(
        self, session: Session, *, workspace_id: str, context: _SendContext
    ) -> None:
        if not self._config.neuro_comment_tdlib_send_enabled:
            return
        if context.target is not None:
            decision = ChannelRulesPolicy().check_target_allowed(
                session, workspace_id=workspace_id, target=context.target
            )
            if not decision.allowed:
                raise NeuroConflictError(
                    decision.reason or "channel rule blocked send",
                    error_code="CHANNEL_RULE_BLOCKED",
                )
        if context.campaign_account is not None and not DefaultAccountReadinessProvider(
            session
        ).is_ready(context.campaign_account.account_id):
            raise NeuroConflictError(
                "account runtime is not ready",
                error_code="ACCOUNT_RUNTIME_NOT_READY",
            )

    def _comment_sender(self) -> TelegramCommentSender:
        if self._sender is None:
            self._sender = build_telegram_comment_sender(self._config)
        return self._sender

    def _validate_send(
        self,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        observed_post: NeuroCommentObservedPost | None,
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
        if observed_post is None:
            raise NeuroConflictError(
                "observed post is required", error_code="OBSERVED_POST_REQUIRED"
            )
        if not observed_post.discussion_message_id:
            raise NeuroConflictError(
                "discussion message is not resolved",
                error_code="DISCUSSION_MESSAGE_NOT_RESOLVED",
            )
        if target is None or not (observed_post.discussion_chat_id or target.discussion_chat_id):
            raise NeuroConflictError("target has no discussion", error_code="TARGET_NO_DISCUSSION")
        if target.status != NeuroTargetStatus.ACTIVE.value:
            raise NeuroConflictError("target is not active", error_code="TARGET_NOT_ACTIVE")
        if (
            campaign_account is None
            or campaign_account.status != NeuroCampaignAccountStatus.ACTIVE.value
        ):
            raise NeuroConflictError("account is not active", error_code="ACCOUNT_NOT_ACTIVE")

    def _reserve_for_attempt(
        self, session: Session, *, context: _SendContext, workspace_id: str
    ) -> RateLimitReservation | None:
        if not getattr(self._config, "neuro_comment_require_redis_limiter_for_send", True):
            return None
        limiter = self._limiter or self._limiter_for_send(session, context.campaign)
        reservation = limiter.reserve(
            RateLimitScope(
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=context.attempt.account_id or context.comment.account_id,
                target_id=context.attempt.target_id or context.comment.target_id,
            )
        )
        if not reservation.allowed:
            context.attempt.status = NeuroAttemptStatus.SKIPPED.value
            context.attempt.error_code = "RATE_LIMIT_DENIED"
            context.attempt.error_message = reservation.reason
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=context.attempt.account_id,
                target_id=context.attempt.target_id,
                observed_post_id=context.attempt.observed_post_id,
                generated_comment_id=context.comment.id,
                attempt_id=context.attempt.id,
                event_type="rate_limit_denied",
                event_level=NeuroEventLevel.WARNING,
                message=reservation.reason or "rate limit denied",
                data={"checked_limits": reservation.checked_limits},
            )
            return None
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=context.attempt.account_id,
            target_id=context.attempt.target_id,
            observed_post_id=context.attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=context.attempt.id,
            event_type="rate_limit_reserved",
            message="neuro-comment send rate limit reserved",
            data={"reservation_id": reservation.reservation_id},
        )
        return reservation

    def _commit_reservation(self, reservation: RateLimitReservation | None) -> None:
        if reservation is None:
            return
        limiter = self._limiter or NeuroCommentRateLimiter(redis_client=self._redis_client)
        limiter.commit(reservation)

    def _rollback_reservation(self, reservation: RateLimitReservation | None) -> None:
        if reservation is None:
            return
        limiter = self._limiter or NeuroCommentRateLimiter(redis_client=self._redis_client)
        limiter.rollback(reservation)

    def _limiter_for_send(
        self, session: Session | None, campaign: NeuroCommentCampaign
    ) -> NeuroCommentRateLimiter:
        limits = None
        if session is not None:
            limits = [
                {
                    "scope_type": item.scope_type,
                    "scope_id": item.scope_id,
                    "limit_type": item.limit_type,
                    "max_value": item.max_value,
                    "window_seconds": item.window_seconds,
                }
                for item in LimitsService().resolve_effective_limits(
                    session, campaign_id=campaign.id, workspace_id=campaign.workspace_id
                )
                if item.enabled
            ]
        return NeuroCommentRateLimiter(redis_client=self._redis_client, limits=limits)

    def _session_for(
        self,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
        campaign: NeuroCommentCampaign,
    ) -> Session | None:
        return object_session(attempt) or object_session(comment) or object_session(campaign)

    def _target_for_send(
        self,
        session: Session | None,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
    ) -> NeuroCommentTarget | None:
        target_id = attempt.target_id or comment.target_id
        if session is None or target_id is None:
            return None
        return (
            session.query(NeuroCommentTarget)
            .filter(
                NeuroCommentTarget.id == target_id,
                NeuroCommentTarget.campaign_id == campaign.id,
            )
            .one_or_none()
        )

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
                AccountHealthService().record_account_flood_wait(
                    session,
                    campaign_id=attempt.campaign_id,
                    account_id=campaign_account.account_id,
                    workspace_id=workspace_id,
                    flood_wait_seconds=error.flood_wait_seconds,
                )
            if attempt.target_id is not None:
                target_health = TargetHealthService()
                target_health.record_target_flood_wait(
                    session, workspace_id=workspace_id, target_id=attempt.target_id
                )
                target_health.suggest_rules_for_target(
                    session, workspace_id=workspace_id, target_id=attempt.target_id
                )
        else:
            attempt.status = NeuroAttemptStatus.FAILED.value
            campaign_account = _campaign_account_or_none(
                session, attempt.campaign_id, attempt.account_id
            )
            if campaign_account is not None:
                AccountHealthService().record_account_send_failure(
                    session,
                    campaign_id=attempt.campaign_id,
                    account_id=campaign_account.account_id,
                    workspace_id=workspace_id,
                    error_code=error.error_code,
                )
            if attempt.target_id is not None:
                target_health = TargetHealthService()
                target_health.record_target_failure(
                    session,
                    workspace_id=workspace_id,
                    target_id=attempt.target_id,
                    error_code=error.error_code,
                )
                target_health.suggest_rules_for_target(
                    session, workspace_id=workspace_id, target_id=attempt.target_id
                )
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
