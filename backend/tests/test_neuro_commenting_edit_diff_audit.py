from __future__ import annotations

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_service import CampaignService
from tests.helpers.factories import seed_two_workspaces


def _seed_comment(
    db_session,
    *,
    workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID,
    generated_text: str = "Первый вариант",
    edited_text: str | None = None,
) -> NeuroCommentGeneratedComment:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=workspace_id,
        actor_user_id="user-1",
        payload={"name": "Edit audit"},
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text=generated_text,
        edited_text=edited_text,
        final_text=edited_text or generated_text,
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=(
            NeuroGeneratedApprovalStatus.EDITED.value
            if edited_text is not None
            else NeuroGeneratedApprovalStatus.PENDING.value
        ),
    )
    db_session.add(comment)
    db_session.commit()
    return comment


def _approve(db_session, comment: NeuroCommentGeneratedComment, *, workspace_id: str):
    approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=workspace_id,
        actor_user_id="user-1",
    )
    db_session.commit()
    return approved, attempt


def _edit_audit_event(db_session) -> NeuroCommentEvent:
    return (
        db_session.query(NeuroCommentEvent).filter_by(event_type="comment_edited_on_approve").one()
    )


def test_approve_unedited_comment_does_not_write_diff_event(db_session) -> None:
    comment = _seed_comment(db_session)

    _approve(db_session, comment, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    count = (
        db_session.query(NeuroCommentEvent)
        .filter_by(event_type="comment_edited_on_approve")
        .count()
    )
    assert count == 0


def test_approve_edited_comment_writes_one_diff_event(db_session) -> None:
    comment = _seed_comment(db_session, edited_text="Новый вариант")

    _approved, attempt = _approve(db_session, comment, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    event = _edit_audit_event(db_session)
    diff = event.data_json["diff"]
    assert event.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert event.generated_comment_id == comment.id
    assert event.attempt_id == attempt.id
    assert diff.startswith("--- generated\n+++ edited")
    assert "-Первый вариант" in diff
    assert "+Новый вариант" in diff


def test_approve_diff_event_redacts_email(db_session) -> None:
    comment = _seed_comment(
        db_session,
        generated_text="Email test@example.com",
        edited_text="Email reviewer@example.com",
    )

    _approve(db_session, comment, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    diff = _edit_audit_event(db_session).data_json["diff"]
    assert "[REDACTED_EMAIL]" in diff
    assert "test@example.com" not in diff
    assert "reviewer@example.com" not in diff


def test_approve_diff_event_redacts_phone(db_session) -> None:
    comment = _seed_comment(
        db_session,
        generated_text="Call +1 555 010 2000",
        edited_text="Call +1 (555) 010-3000",
    )

    _approve(db_session, comment, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    diff = _edit_audit_event(db_session).data_json["diff"]
    assert "[REDACTED_PHONE]" in diff
    assert "+1 555 010 2000" not in diff
    assert "+1 (555) 010-3000" not in diff


def test_approve_diff_event_truncates_long_diff(db_session) -> None:
    comment = _seed_comment(db_session, generated_text="short", edited_text="x" * 5000)

    _approve(db_session, comment, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    diff = _edit_audit_event(db_session).data_json["diff"]
    assert len(diff) <= 4096
    assert diff.endswith("[TRUNCATED]")


def test_approve_diff_event_uses_comment_workspace_id(db_session) -> None:
    _own_workspace, foreign_workspace = seed_two_workspaces(db_session)
    comment = _seed_comment(db_session, workspace_id=foreign_workspace, edited_text="Новый вариант")

    _approve(db_session, comment, workspace_id=foreign_workspace)

    event = _edit_audit_event(db_session)
    assert event.workspace_id == foreign_workspace
    assert event.workspace_id != DEFAULT_LOCAL_WORKSPACE_ID
