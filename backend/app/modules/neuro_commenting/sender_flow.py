from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    utc_now,
)
from app.modules.human_behavior.interfaces import (
    emit_typing,
    get_or_create_baseline,
    randomize_for_session,
    run_before_send,
    total_duration,
)
from app.observability.safety_metrics import safety_metrics
from app.services.idempotency_keys import (
    IdempotencyConflict,
    generate as generate_idempotency_key,
    reserve_in_redis,
)
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting.enums import (
    NeuroAttemptStatus,
    NeuroCampaignAccountStatus,
    NeuroCampaignStatus,
    NeuroEventLevel,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    NeuroTargetStatus,
)
from app.modules.neuro_commenting.errors import NeuroConflictError, NeuroValidationError
from app.modules.neuro_commenting.rate_limiter import RateLimitScope
from app.modules.neuro_commenting.sender_contracts import (
    BehaviorEmulatorSendPlan,
    TelegramCommentSendError,
    TelegramCommentSender,
    _SendContext,
    _comment_text,
    _discussion_chat_id,
    build_telegram_comment_sender,
)


class SenderFlowMixin:
    def send_attempt(
        self, session: Session, *, attempt_id: str, workspace_id: str
    ) -> NeuroCommentAttempt:
        context = self._load_context(session, attempt_id=attempt_id, workspace_id=workspace_id)
        attempt = context.attempt
        if attempt.status == NeuroAttemptStatus.SENT.value and attempt.telegram_message_id:
            return attempt
        self._validate_context(context)
        self._raise_if_send_disabled(session, workspace_id=workspace_id, context=context)
        if self._block_by_safety_gate(session, workspace_id=workspace_id, context=context):
            return attempt
        if self._block_by_channel_rule(session, workspace_id=workspace_id, context=context):
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
        discussion_chat_id = _discussion_chat_id(context)
        final_text = _comment_text(context)
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
        self._commit_reservation(reservation)
        self._mark_attempt_sent(
            session,
            workspace_id=workspace_id,
            context=context,
            result=result,
            idempotency_key=idem.key,
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
            decision = ChannelRulesService().evaluate_target_allowed(
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
