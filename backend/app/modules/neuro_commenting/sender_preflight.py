from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
)
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.account_selector import DefaultAccountReadinessProvider
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting.enums import (
    NeuroAttemptStatus,
    NeuroEventLevel,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
)
from app.modules.neuro_commenting.errors import NeuroConflictError, NeuroRuntimeDisabledError
from app.modules.neuro_commenting.sender_contracts import (
    PreparedSend,
    _SendContext,
    _campaign_account_or_none,
    _evaluate_commenting_gate,
    _target_or_none,
)


class SenderPreflightMixin:
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

    def _raise_if_send_disabled(
        self, session: Session, *, workspace_id: str, context: _SendContext
    ) -> None:
        if self._config.neuro_comment_tdlib_send_enabled:
            return
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=context.campaign.id,
            account_id=context.attempt.account_id,
            target_id=context.attempt.target_id,
            generated_comment_id=context.comment.id,
            attempt_id=context.attempt.id,
            event_type="manual_send_blocked",
            message="TDLib neuro-comment sending is disabled.",
            data={"error_code": "NEURO_COMMENT_SEND_DISABLED"},
        )
        raise NeuroRuntimeDisabledError(
            "TDLib neuro-comment sending is disabled.",
            error_code="NEURO_COMMENT_SEND_DISABLED",
        )

    def _block_by_channel_rule(
        self, session: Session, *, workspace_id: str, context: _SendContext
    ) -> bool:
        if context.target is None:
            return False
        decision = ChannelRulesService().evaluate_target_allowed(
            session, workspace_id=workspace_id, target=context.target
        )
        if decision.allowed:
            return False
        attempt = context.attempt
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
        return True

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
            decision = ChannelRulesService().evaluate_target_allowed(
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
