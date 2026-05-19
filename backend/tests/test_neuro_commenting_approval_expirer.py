from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentCampaign,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroGeneratedApprovalStatus,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting.approval_expirer import ApprovalExpirer


def _seed_campaign(db_session) -> NeuroCommentCampaign:
    campaign = NeuroCommentCampaign(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name="Expirer test campaign",
        status="running",
        mode="all_posts",
        work_mode="manual",
        approval_mode="manual_required",
        send_mode="manual_approval",
        send_strategy="comment",
        rotation_strategy="round_robin",
        language_mode="auto",
        dry_run=True,
        auto_send_enabled=False,
        safety_enabled=True,
    )
    db_session.add(campaign)
    db_session.flush()
    return campaign


def _seed_pending_comment(
    db_session,
    campaign: NeuroCommentCampaign,
    *,
    created_at: datetime,
    approval_status: str = NeuroGeneratedApprovalStatus.PENDING.value,
) -> NeuroCommentGeneratedComment:
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        generated_text="placeholder",
        safety_status=NeuroSafetyStatus.PASSED.value,
        approval_status=approval_status,
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(comment)
    db_session.flush()
    return comment


def test_expires_pending_comments_older_than_ttl(db_session) -> None:
    campaign = _seed_campaign(db_session)
    now = datetime.now(UTC)
    stale = _seed_pending_comment(db_session, campaign, created_at=now - timedelta(hours=5))
    fresh = _seed_pending_comment(db_session, campaign, created_at=now - timedelta(minutes=10))

    expired = ApprovalExpirer().expire_stale_approvals(
        db_session, ttl_seconds=14400, now=now
    )

    db_session.refresh(stale)
    db_session.refresh(fresh)
    assert expired == 1
    assert stale.approval_status == NeuroGeneratedApprovalStatus.EXPIRED.value
    assert fresh.approval_status == NeuroGeneratedApprovalStatus.PENDING.value


def test_does_not_touch_non_pending_comments(db_session) -> None:
    campaign = _seed_campaign(db_session)
    now = datetime.now(UTC)
    approved = _seed_pending_comment(
        db_session,
        campaign,
        created_at=now - timedelta(days=1),
        approval_status=NeuroGeneratedApprovalStatus.APPROVED.value,
    )
    rejected = _seed_pending_comment(
        db_session,
        campaign,
        created_at=now - timedelta(days=1),
        approval_status=NeuroGeneratedApprovalStatus.REJECTED.value,
    )

    expired = ApprovalExpirer().expire_stale_approvals(
        db_session, ttl_seconds=14400, now=now
    )

    db_session.refresh(approved)
    db_session.refresh(rejected)
    assert expired == 0
    assert approved.approval_status == NeuroGeneratedApprovalStatus.APPROVED.value
    assert rejected.approval_status == NeuroGeneratedApprovalStatus.REJECTED.value


def test_writes_audit_event_on_expiration(db_session) -> None:
    campaign = _seed_campaign(db_session)
    now = datetime.now(UTC)
    _seed_pending_comment(db_session, campaign, created_at=now - timedelta(hours=10))

    ApprovalExpirer().expire_stale_approvals(db_session, ttl_seconds=3600, now=now)

    events = (
        db_session.query(NeuroCommentEvent)
        .filter(NeuroCommentEvent.event_type == "approval_expired")
        .all()
    )
    assert len(events) == 1
    assert events[0].workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert events[0].event_level == "warning"
    assert events[0].data_json["ttl_seconds"] == 3600


def test_rejects_invalid_ttl(db_session) -> None:
    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        ApprovalExpirer().expire_stale_approvals(db_session, ttl_seconds=0)
