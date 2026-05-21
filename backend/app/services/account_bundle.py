"""Optimized account loading for dashboard with eager-loaded relationships."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, Account, Job


def get_account_dashboard_bundle(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Account | None:
    """Load account with all relationships needed for dashboard in 1 query.

    Eager-loads: profile_state, runtime_state, profile_audio_state.
    Story posts are loaded separately via list_story_posts() because they
    require status filtering and ordering.
    """
    load_options = (
        joinedload(Account.profile_state),
        joinedload(Account.runtime_state),
        joinedload(Account.profile_audio_state),
    )
    target_workspace_id = workspace_id or DEFAULT_LOCAL_WORKSPACE_ID
    statement = (
        select(Account)
        .where(Account.id == account_id, Account.workspace_id == target_workspace_id)
        .options(*load_options)
    )
    return session.execute(statement).scalars().unique().first()


def get_latest_job_for_account(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Job | None:
    """Get the most recent job for an account in a single query."""
    target_workspace_id = workspace_id or DEFAULT_LOCAL_WORKSPACE_ID
    statement = (
        select(Job)
        .where(Job.account_id == account_id, Job.workspace_id == target_workspace_id)
        .order_by(Job.queued_at.desc())
        .limit(1)
    )
    return session.execute(statement).scalars().first()
