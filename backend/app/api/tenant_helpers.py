"""API-layer helpers for workspace-scoped entity lookups.

These helpers raise ``AppError`` with standard non-leaking error codes
when the requested entity does not exist or belongs to a foreign workspace.
Pure DB lookup functions live in ``app.services.tenant_scope``.
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Account, Job
from app.services.auth_context import AuthContext
from app.services.tenant_scope import get_account_for_workspace, get_job_for_workspace


def require_account_in_workspace(
    session: Session,
    account_id: str,
    auth: AuthContext,
) -> Account:
    """Load an account scoped to the caller's workspace or raise 404."""
    account = get_account_for_workspace(session, account_id, auth.workspace_id)
    if account is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
            message="account not found",
        )
    return account


def require_job_in_workspace(
    session: Session,
    job_id: str,
    auth: AuthContext,
) -> Job:
    """Load a job scoped to the caller's workspace or raise 404."""
    job = get_job_for_workspace(session, job_id, auth.workspace_id)
    if job is None:
        raise AppError(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="JOB_NOT_FOUND",
            error_class="not_found",
            message="job not found",
        )
    return job
