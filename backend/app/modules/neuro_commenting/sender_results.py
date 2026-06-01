from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportPrivateUsage=false, reportUnknownMemberType=false

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import (
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentGeneratedComment,
    utc_now,
)
from app.modules.account_safety.interfaces import (
    SafetyGateReservation,
    release as release_gate_reservation,
    reserve as reserve_gate_slot,
)
from app.modules.neuro_commenting.account_health_service import AccountHealthService
from app.modules.neuro_commenting.enums import NeuroAttemptStatus, NeuroEventLevel
from app.modules.neuro_commenting.sender_contracts import (
    SentCommentResult,
    TelegramCommentSendError,
    _SendContext,
    _campaign_account_or_none,
)
from app.modules.neuro_commenting.target_health_service import TargetHealthService

_INT_COERCION_ERRORS = (TypeError, ValueError)


class SenderResultsMixin:
    def _mark_attempt_sent(
        self,
        session: Session,
        *,
        workspace_id: str,
        context: _SendContext,
        result: SentCommentResult,
        idempotency_key: str,
    ) -> None:
        attempt = context.attempt
        try:
            attempt.external_message_id_provisional = int(result.telegram_message_id)
        except _INT_COERCION_ERRORS:
            # Non-numeric message id is acceptable; canonical id is stored below.
            pass
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
        assert context.target is not None
        context.target.last_commented_at = result.sent_at
        self._write_outbox_event(
            session,
            workspace_id=workspace_id,
            context=context,
            event_type="comment_sent_provisional",
            data={"attempt_id": attempt.id, "idempotency_key": idempotency_key},
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
