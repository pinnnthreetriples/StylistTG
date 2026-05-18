from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import NeuroCommentAttempt, NeuroCommentGeneratedComment, new_id
from app.services.neuro_commenting.analytics_service import AnalyticsService
from app.services.neuro_commenting.enums import (
    NeuroAttemptStatus,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
)
from app.services.neuro_commenting import repository


class ApprovalService:
    def __init__(self, analytics: AnalyticsService | None = None) -> None:
        self._analytics = analytics or AnalyticsService()

    def edit_comment(
        self,
        session: Session,
        *,
        comment_id: str,
        workspace_id: str,
        actor_user_id: str | None,
        edited_text: str,
    ) -> NeuroCommentGeneratedComment:
        comment = repository.require_generated_comment(
            session, comment_id=comment_id, workspace_id=workspace_id
        )
        if not edited_text.strip():
            raise ValueError("edited text is required")
        comment.edited_text = edited_text.strip()
        comment.final_text = comment.edited_text
        comment.approval_status = NeuroGeneratedApprovalStatus.EDITED.value
        comment.updated_at = datetime.now(UTC)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=comment.campaign_id,
            account_id=comment.account_id,
            target_id=comment.target_id,
            observed_post_id=comment.observed_post_id,
            generated_comment_id=comment.id,
            event_type="comment_edited",
            message="generated comment edited",
            data={"actor_user_id": actor_user_id},
        )
        return comment

    def approve_comment(
        self,
        session: Session,
        *,
        comment_id: str,
        workspace_id: str,
        actor_user_id: str | None,
    ) -> tuple[NeuroCommentGeneratedComment, NeuroCommentAttempt]:
        comment = repository.require_generated_comment(
            session, comment_id=comment_id, workspace_id=workspace_id
        )
        if comment.safety_status == NeuroSafetyStatus.BLOCKED.value:
            raise ValueError("blocked comment cannot be approved")
        comment.approval_status = NeuroGeneratedApprovalStatus.APPROVED.value
        comment.final_text = comment.edited_text or comment.generated_text
        comment.approved_by = actor_user_id
        comment.approved_at = datetime.now(UTC)
        attempt = NeuroCommentAttempt(
            id=new_id(),
            campaign_id=comment.campaign_id,
            generated_comment_id=comment.id,
            account_id=comment.account_id,
            target_id=comment.target_id,
            observed_post_id=comment.observed_post_id,
            status=NeuroAttemptStatus.CREATED.value,
        )
        session.add(attempt)
        session.flush()
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=comment.campaign_id,
            account_id=comment.account_id,
            target_id=comment.target_id,
            observed_post_id=comment.observed_post_id,
            generated_comment_id=comment.id,
            attempt_id=attempt.id,
            event_type="comment_approved",
            message="generated comment approved and send attempt prepared",
            data={"actor_user_id": actor_user_id, "auto_send": False},
        )
        return comment, attempt

    def reject_comment(
        self,
        session: Session,
        *,
        comment_id: str,
        workspace_id: str,
        actor_user_id: str | None,
        reason: str,
    ) -> NeuroCommentGeneratedComment:
        comment = repository.require_generated_comment(
            session, comment_id=comment_id, workspace_id=workspace_id
        )
        comment.approval_status = NeuroGeneratedApprovalStatus.REJECTED.value
        comment.rejected_reason = reason
        comment.updated_at = datetime.now(UTC)
        self._analytics.write_event(
            session,
            workspace_id=workspace_id,
            campaign_id=comment.campaign_id,
            account_id=comment.account_id,
            target_id=comment.target_id,
            observed_post_id=comment.observed_post_id,
            generated_comment_id=comment.id,
            event_type="comment_rejected",
            message="generated comment rejected",
            data={"actor_user_id": actor_user_id},
        )
        return comment
