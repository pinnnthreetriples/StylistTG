"""Optimized account loading for dashboard with eager-loaded relationships."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Account, Job


def get_account_dashboard_bundle(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Account | None:
    """Load account with all relationships needed for dashboard in 1 query.

    Eager-loads: profile_state, runtime_state, profile_audio_state.
    Story posts are loaded separately via list_story_posts() because they
    require status filtering and ordering.
    """
    statement = (
        select(Account)
        .where(Account.id == account_id)
        .options(
            joinedload(Account.profile_state),
            joinedload(Account.runtime_state),
            joinedload(Account.profile_audio_state),
        )
    )
    if workspace_id is not None:
        statement = statement.where(Account.workspace_id == workspace_id)
    return session.execute(statement).scalars().unique().first()


def get_latest_job_for_account(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Job | None:
    """Get the most recent job for an account in a single query."""
    statement = (
        select(Job).where(Job.account_id == account_id).order_by(Job.queued_at.desc()).limit(1)
    )
    if workspace_id is not None:
        statement = statement.where(Job.workspace_id == workspace_id)
    return session.execute(statement).scalars().first()
