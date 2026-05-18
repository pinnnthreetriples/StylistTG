from __future__ import annotations

from dataclasses import dataclass

from app.models import NeuroCommentAttempt, NeuroCommentCampaign, NeuroCommentGeneratedComment
from app.services.neuro_commenting.enums import NeuroAttemptStatus, NeuroSendMode


@dataclass(frozen=True)
class PreparedSend:
    allowed: bool
    reason: str | None = None


class SenderService:
    def prepare_send(
        self,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
    ) -> PreparedSend:
        if campaign.dry_run or not campaign.auto_send_enabled:
            return PreparedSend(allowed=False, reason="auto_send_disabled")
        if campaign.send_mode != NeuroSendMode.AUTO.value:
            return PreparedSend(allowed=False, reason="manual_send_required")
        return PreparedSend(allowed=False, reason="tdlib_sender_not_implemented")

    def send_comment(
        self,
        *,
        campaign: NeuroCommentCampaign,
        comment: NeuroCommentGeneratedComment,
        attempt: NeuroCommentAttempt,
    ) -> NeuroCommentAttempt:
        attempt.status = NeuroAttemptStatus.SKIPPED.value
        attempt.error_code = "AUTO_SEND_DISABLED"
        attempt.error_message = "TDLib comment sender is not enabled in foundation skeleton"
        return attempt
