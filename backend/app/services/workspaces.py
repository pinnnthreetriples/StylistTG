from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    User,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
    WorkspaceRole,
    UserStatus,
    WorkspaceStatus,
    utc_now,
)

DEFAULT_LOCAL_EMAIL = "local@stylisttg.local"
DEFAULT_LOCAL_WORKSPACE_SLUG = "local"


def ensure_default_workspace(session: Session) -> tuple[User, Workspace, WorkspaceMember]:
    now = utc_now()
    user = session.get(User, DEFAULT_LOCAL_USER_ID)
    if user is None:
        user = User(
            id=DEFAULT_LOCAL_USER_ID,
            email=DEFAULT_LOCAL_EMAIL,
            display_name="Local Operator",
            external_auth_provider="local",
            external_auth_user_id="local-operator",
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add(user)

    workspace = session.get(Workspace, DEFAULT_LOCAL_WORKSPACE_ID)
    if workspace is None:
        workspace = Workspace(
            id=DEFAULT_LOCAL_WORKSPACE_ID,
            name="Local Workspace",
            slug=DEFAULT_LOCAL_WORKSPACE_SLUG,
            owner_user_id=DEFAULT_LOCAL_USER_ID,
            status=WorkspaceStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        session.add(workspace)

    member = (
        session.query(WorkspaceMember)
        .filter_by(workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, user_id=DEFAULT_LOCAL_USER_ID)
        .one_or_none()
    )
    if member is None:
        member = WorkspaceMember(
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            user_id=DEFAULT_LOCAL_USER_ID,
            role=WorkspaceRole.OWNER,
            created_at=now,
            updated_at=now,
        )
        session.add(member)

    plan = session.get(WorkspacePlan, DEFAULT_LOCAL_WORKSPACE_ID)
    if plan is None:
        session.add(
            WorkspacePlan(
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                plan_code="local",
                billing_status="active",
                max_accounts=1000,
                max_jobs_per_day=10000,
                max_batch_size=1000,
                max_storage_mb=10240,
                max_team_members=10,
                created_at=now,
                updated_at=now,
            )
        )

    session.flush()
    return user, workspace, member
