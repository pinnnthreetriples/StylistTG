from __future__ import annotations

from difflib import unified_diff
import re

from sqlalchemy.orm import Session

from app.models import NeuroCommentAttempt, NeuroCommentGeneratedComment, new_id, utc_now
from app.services.secret_redaction import redact_text
from app.modules.neuro_commenting.analytics_service import AnalyticsService
from app.modules.neuro_commenting.enums import (
    NeuroAttemptStatus,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
)
from app.modules.neuro_commenting import repository

_EMAIL_RE = re.compile(r"\b[\w.-]+@[\w.-]+\.\w{2,}\b")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,}\d")
_MAX_AUDIT_DIFF_CHARS = 4096
_TRUNCATED_MARKER = "\n[TRUNCATED]"


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
        comment.updated_at = utc_now()
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
        comment.approved_at = utc_now()
        attempt = repository.get_attempt_for_generated_comment(
            session, generated_comment_id=comment.id
        )
        if attempt is None:
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
        _maybe_audit_edit(
            self._analytics,
            session,
            comment=comment,
            attempt_id=attempt.id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
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
        comment.updated_at = utc_now()
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


def _maybe_audit_edit(
    analytics: AnalyticsService,
    session: Session,
    *,
    comment: NeuroCommentGeneratedComment,
    attempt_id: str,
    workspace_id: str,
    actor_user_id: str | None,
) -> None:
    edited_text = comment.edited_text
    if edited_text is None or edited_text == comment.generated_text:
        return
    diff_lines = list(
        unified_diff(
            comment.generated_text.splitlines(),
            edited_text.splitlines(),
            fromfile="generated",
            tofile="edited",
            lineterm="",
            n=3,
        )
    )
    analytics.write_event(
        session,
        workspace_id=workspace_id,
        campaign_id=comment.campaign_id,
        account_id=comment.account_id,
        target_id=comment.target_id,
        observed_post_id=comment.observed_post_id,
        generated_comment_id=comment.id,
        attempt_id=attempt_id,
        event_type="comment_edited_on_approve",
        message="generated comment edited during approval",
        data={
            "diff": _redact_diff("\n".join(diff_lines)),
            "user_id": actor_user_id,
            "generated_length": len(comment.generated_text),
            "edited_length": len(edited_text),
            "diff_lines": len(diff_lines),
        },
    )


def _redact_diff(diff: str) -> str:
    redacted = redact_text(diff)
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    if len(redacted) <= _MAX_AUDIT_DIFF_CHARS:
        return redacted
    budget = _MAX_AUDIT_DIFF_CHARS - len(_TRUNCATED_MARKER)
    return redacted[:budget].rstrip() + _TRUNCATED_MARKER
