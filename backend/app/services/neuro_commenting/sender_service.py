from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy.orm import Session, object_session

from app.config import Settings, settings
from app.contracts.safety_gate import SafetyGateVerdict
from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    utc_now,
)
from app.services.account_safety_gate import evaluate as evaluate_safety_gate
from app.services.human_behavior.behavior_profile import (
    get_or_create_baseline,
    randomize_for_session,
)
from app.services.human_behavior.decoy_actions import DecoyAction, run_before_send
from app.services.human_behavior.typing_emulator import (
    TypingFragment,
    emit_typing,
    total_duration,
)
from app.services.idempotency_keys import (
    IdempotencyConflict,
    generate as generate_idempotency_key,
    reserve_in_redis,
)
from app.observability.safety_metrics import safety_metrics
from app.services.safety_gate_reserve import (
    SafetyGateReservation,
    release as release_gate_reservation,
    reserve as reserve_gate_slot,
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

_INT_COERCION_ERRORS = (TypeError, ValueError)


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


class SenderService:
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
        if self._block_by_safety_gate(session, workspace_id=workspace_id, context=context):
            return attempt
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
        idem = generate_idempotency_key(attempt.id)
        attempt.idempotency_key = idem.key
        attempt.status = NeuroAttemptStatus.SENDING.value
        session.flush()

        redis_client = self._redis_client
        if redis_client is not None and not reserve_in_redis(
            redis_client, key=idem.key, attempt_id=attempt.id
        ):
            raise IdempotencyConflict("idempotency_key collision")

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
            data={"idempotency_key": idem.key},
        )
        # F-001/F-002 fix: every error path must release reservations AND
        # finalize the attempt (status, failed_at, audit event). The original
        # non-FLOOD_WAIT branch only set error_code/message and left status =
        # SENDING forever; unexpected exceptions leaked both the rate-limiter
        # reservation and the Redis gate slot until their TTL fired.
        gate_released = False
        try:
            reply_to_message_id = str(context.observed_post.discussion_message_id)
            self._prepare_behavior_emulator_before_send(
                session,
                workspace_id=workspace_id,
                context=context,
                discussion_chat_id=str(discussion_chat_id),
                reply_to_message_id=reply_to_message_id,
                final_text=final_text,
            )
            with safety_metrics.attempt_send_duration(strategy=attempt.send_strategy):
                result = self._comment_sender().send_comment(
                    account_id=str(attempt.account_id),
                    discussion_chat_id=str(discussion_chat_id),
                    reply_to_message_id=reply_to_message_id,
                    text=final_text,
                    random_id=idem.random_id_hash,
                )
        except TelegramCommentSendError as exc:
            self._rollback_reservation(reservation)
            self._release_gate_reservation()
            gate_released = True
            self._mark_send_error(session, workspace_id=workspace_id, attempt=attempt, error=exc)
            return attempt
        except Exception as exc:  # noqa: BLE001 — catch-all required to release reservations
            self._rollback_reservation(reservation)
            self._release_gate_reservation()
            gate_released = True
            attempt.status = NeuroAttemptStatus.FAILED.value
            attempt.failed_at = utc_now()
            attempt.error_code = "sender_unexpected_error"
            attempt.error_message = f"{type(exc).__name__}: {exc}"[:300]
            self._analytics.write_event(
                session,
                workspace_id=workspace_id,
                campaign_id=context.campaign.id,
                account_id=attempt.account_id,
                target_id=attempt.target_id,
                observed_post_id=attempt.observed_post_id,
                generated_comment_id=context.comment.id,
                attempt_id=attempt.id,
                event_type="comment_send_unexpected_error",
                event_level=NeuroEventLevel.ERROR,
                message=f"{type(exc).__name__}: {str(exc)[:200]}",
                data={"error_class": type(exc).__name__},
            )
            raise
        finally:
            if not gate_released:
                self._release_gate_reservation()
        try:
            attempt.external_message_id_provisional = int(result.telegram_message_id)
        except _INT_COERCION_ERRORS:
            pass
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
        self._write_outbox_event(
            session,
            workspace_id=workspace_id,
            context=context,
            event_type="comment_sent_provisional",
            data={"attempt_id": attempt.id, "idempotency_key": idem.key},
        )
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
        self._release_gate_reservation()
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
        now = utc_now()
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
        now = utc_now()
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
        verdict = _evaluate_commenting_gate(session, workspace_id=workspace_id, context=context)
        if verdict is not None and verdict.severity == "blocked":
            raise NeuroConflictError(
                "account safety gate blocked send",
                error_code="ACCOUNT_SAFETY_BLOCKED",
            )

    def _block_by_safety_gate(
        self, session: Session, *, workspace_id: str, context: _SendContext
    ) -> bool:
        verdict = _evaluate_commenting_gate(session, workspace_id=workspace_id, context=context)
        if verdict is None or verdict.severity != "blocked":
            # Attempt atomic gate reserve if redis available
            self._gate_reservation = self._try_gate_reserve(context)
            if self._gate_reservation is not None and not self._gate_reservation.reserved:
                context.attempt.status = NeuroAttemptStatus.SKIPPED.value
                context.attempt.error_code = "GATE_CONCURRENCY_LIMIT"
                context.attempt.error_message = "Account concurrency limit reached."
                self._analytics.write_event(
                    session,
                    workspace_id=workspace_id,
                    campaign_id=context.campaign.id,
                    account_id=context.attempt.account_id,
                    target_id=context.attempt.target_id,
                    observed_post_id=context.attempt.observed_post_id,
                    generated_comment_id=context.comment.id,
                    attempt_id=context.attempt.id,
                    event_type="neuro_comment_send_blocked_by_gate_concurrency",
                    event_level=NeuroEventLevel.WARNING,
                    message="neuro-comment send blocked by gate concurrency limit",
                    data={"current_count": self._gate_reservation.current_count},
                )
                return True
            return False
        context.attempt.status = NeuroAttemptStatus.SKIPPED.value
        context.attempt.error_code = "ACCOUNT_SAFETY_BLOCKED"
        context.attempt.error_message = "; ".join(reason.code for reason in verdict.reasons)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=context.attempt.account_id,
            target_id=context.attempt.target_id,
            observed_post_id=context.attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=context.attempt.id,
            event_type="neuro_comment_send_blocked_by_gate",
            event_level=NeuroEventLevel.WARNING,
            message="neuro-comment send blocked by account safety gate",
            data={"reasons": [reason.code for reason in verdict.reasons]},
        )
        return True

    def _write_outbox_event(
        self,
        session: Session,
        *,
        workspace_id: str,
        context: _SendContext,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        event = NeuroCommentEvent(
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=context.attempt.account_id,
            target_id=context.attempt.target_id,
            observed_post_id=context.attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=context.attempt.id,
            event_type=event_type,
            event_level="info",
            message=f"outbox: {event_type}",
            data_json=data,
            is_published=False,
        )
        session.add(event)

    def _try_gate_reserve(self, context: _SendContext) -> SafetyGateReservation | None:
        """Attempt atomic gate reserve if redis_client is available."""
        if self._redis_client is None:
            return None
        account_id = context.attempt.account_id or context.comment.account_id
        if account_id is None:
            return None
        return reserve_gate_slot(
            self._redis_client,
            account_id=account_id,
            intent="commenting",
        )

    def _release_gate_reservation(self) -> None:
        """Release gate reservation slot if one was acquired."""
        if self._gate_reservation is not None and self._gate_reservation.reserved:
            if self._redis_client is not None:
                release_gate_reservation(self._redis_client, reservation=self._gate_reservation)
            self._gate_reservation = None

    def _comment_sender(self) -> TelegramCommentSender:
        if self._sender is None:
            self._sender = build_telegram_comment_sender(self._config)
        return self._sender

    def _prepare_behavior_emulator_before_send(
        self,
        session: Session,
        *,
        workspace_id: str,
        context: _SendContext,
        discussion_chat_id: str,
        reply_to_message_id: str,
        final_text: str,
    ) -> None:
        if not getattr(self._config, "behavior_emulator_live_send_enabled", False):
            return

        account_id = context.attempt.account_id or context.comment.account_id
        if account_id is None:
            return

        baseline = get_or_create_baseline(
            session,
            account_id=account_id,
            workspace_id=workspace_id,
        )
        profile = randomize_for_session(baseline)
        typing_fragments = (
            emit_typing(final_text, profile.typing_speed_cpm)
            if profile.typing_speed_cpm is not None
            else []
        )
        decoy_actions = run_before_send(account_id, profile.profile_view_probability)
        plan = BehaviorEmulatorSendPlan(
            typing_fragments=tuple(typing_fragments),
            decoy_actions=tuple(decoy_actions),
            typing_duration_seconds=round(total_duration(typing_fragments), 3),
        )
        self._behavior_emulator_hook.before_send(
            account_id=account_id,
            discussion_chat_id=discussion_chat_id,
            reply_to_message_id=reply_to_message_id,
            plan=plan,
        )
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=account_id,
            target_id=context.attempt.target_id,
            observed_post_id=context.attempt.observed_post_id,
            generated_comment_id=context.comment.id,
            attempt_id=context.attempt.id,
            event_type="behavior_emulator_live_send_prepared",
            message="behavior emulator send plan prepared",
            data={
                "behavior_profile_id": baseline.id,
                "typing_fragment_count": len(typing_fragments),
                "typing_duration_seconds": plan.typing_duration_seconds,
                "decoy_action_count": len(decoy_actions),
                "decoy_action_kinds": [action.kind for action in decoy_actions],
            },
        )

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
        now = utc_now()
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
