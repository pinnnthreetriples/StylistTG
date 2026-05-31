from __future__ import annotations


from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Account,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentGeneratedComment,
    NeuroCommentTarget,
)

def get_campaign(
    session: Session,
    *,
    campaign_id: str,
    workspace_id: str,
) -> NeuroCommentCampaign | None:
    return (
        session.query(NeuroCommentCampaign)
        .filter(
            NeuroCommentCampaign.id == campaign_id,
            NeuroCommentCampaign.workspace_id == workspace_id,
        )
        .one_or_none()
    )


def require_campaign(
    session: Session,
    *,
    campaign_id: str,
    workspace_id: str,
) -> NeuroCommentCampaign:
    campaign = get_campaign(session, campaign_id=campaign_id, workspace_id=workspace_id)
    if campaign is None:
        raise ValueError("campaign not found")
    return campaign


def list_campaigns(
    session: Session,
    *,
    workspace_id: str,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentCampaign], int]:
    query = session.query(NeuroCommentCampaign).filter(
        NeuroCommentCampaign.workspace_id == workspace_id
    )
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentCampaign.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_account_for_workspace(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> Account | None:
    return (
        session.query(Account)
        .filter(Account.id == account_id, Account.workspace_id == workspace_id)
        .one_or_none()
    )


def get_campaign_account(
    session: Session,
    *,
    campaign_id: str,
    account_id: str,
) -> NeuroCommentCampaignAccount | None:
    return (
        session.query(NeuroCommentCampaignAccount)
        .filter(
            NeuroCommentCampaignAccount.campaign_id == campaign_id,
            NeuroCommentCampaignAccount.account_id == account_id,
        )
        .one_or_none()
    )


def list_campaign_accounts(
    session: Session,
    *,
    campaign_id: str,
) -> list[NeuroCommentCampaignAccount]:
    return (
        session.query(NeuroCommentCampaignAccount)
        .filter(NeuroCommentCampaignAccount.campaign_id == campaign_id)
        .order_by(NeuroCommentCampaignAccount.rotation_order.asc())
        .all()
    )


def list_campaign_accounts_page(
    session: Session,
    *,
    campaign_id: str,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentCampaignAccount], int]:
    query = session.query(NeuroCommentCampaignAccount).filter(
        NeuroCommentCampaignAccount.campaign_id == campaign_id
    )
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentCampaignAccount.rotation_order.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_target(
    session: Session,
    *,
    target_id: str,
    campaign_id: str,
) -> NeuroCommentTarget | None:
    return (
        session.query(NeuroCommentTarget)
        .filter(
            NeuroCommentTarget.id == target_id,
            NeuroCommentTarget.campaign_id == campaign_id,
        )
        .one_or_none()
    )


def require_target(
    session: Session,
    *,
    target_id: str,
    campaign_id: str,
) -> NeuroCommentTarget:
    target = get_target(session, target_id=target_id, campaign_id=campaign_id)
    if target is None:
        raise ValueError("target not found")
    return target


def list_targets(
    session: Session,
    *,
    campaign_id: str,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentTarget], int]:
    query = session.query(NeuroCommentTarget).filter(NeuroCommentTarget.campaign_id == campaign_id)
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentTarget.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def list_generated_comments(
    session: Session,
    *,
    workspace_id: str,
    campaign_id: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> tuple[list[NeuroCommentGeneratedComment], int]:
    query = (
        session.query(NeuroCommentGeneratedComment)
        .join(NeuroCommentCampaign)
        .filter(NeuroCommentCampaign.workspace_id == workspace_id)
    )
    if campaign_id is not None:
        query = query.filter(NeuroCommentGeneratedComment.campaign_id == campaign_id)
    total = int(query.with_entities(func.count()).scalar() or 0)
    items = (
        query.order_by(NeuroCommentGeneratedComment.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_generated_comment(
    session: Session,
    *,
    comment_id: str,
    workspace_id: str,
) -> NeuroCommentGeneratedComment | None:
    return (
        session.query(NeuroCommentGeneratedComment)
        .join(NeuroCommentCampaign)
        .filter(
            NeuroCommentGeneratedComment.id == comment_id,
            NeuroCommentCampaign.workspace_id == workspace_id,
        )
        .one_or_none()
    )


def require_generated_comment(
    session: Session,
    *,
    comment_id: str,
    workspace_id: str,
) -> NeuroCommentGeneratedComment:
    comment = get_generated_comment(session, comment_id=comment_id, workspace_id=workspace_id)
    if comment is None:
        raise ValueError("generated comment not found")
    return comment


def get_generated_comment_for_observed_post(
    session: Session,
    *,
    observed_post_id: str,
) -> NeuroCommentGeneratedComment | None:
    return (
        session.query(NeuroCommentGeneratedComment)
        .filter(NeuroCommentGeneratedComment.observed_post_id == observed_post_id)
        .order_by(NeuroCommentGeneratedComment.created_at.asc())
        .first()
    )
