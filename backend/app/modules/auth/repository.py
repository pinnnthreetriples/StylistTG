from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    User,
    UserStatus,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
    WorkspaceRole,
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


def get_or_create_external_user(
    session: Session,
    *,
    provider: str,
    external_user_id: str,
    email: str,
    display_name: str | None = None,
) -> User:
    user = (
        session.query(User)
        .filter_by(external_auth_provider=provider, external_auth_user_id=external_user_id)
        .one_or_none()
    )
    if user is None:
        user = User(
            email=email,
            display_name=display_name,
            external_auth_provider=provider,
            external_auth_user_id=external_user_id,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
    else:
        user.email = email or user.email
        user.display_name = display_name or user.display_name
        user.updated_at = utc_now()
    session.flush()
    return user


def resolve_workspace_membership(
    session: Session,
    *,
    user: User,
    requested_workspace_id: str | None,
) -> WorkspaceMember | None:
    if requested_workspace_id:
        return (
            session.query(WorkspaceMember)
            .filter_by(user_id=user.id, workspace_id=requested_workspace_id)
            .one_or_none()
        )
    return ensure_personal_workspace(session, user=user)


def ensure_personal_workspace(session: Session, *, user: User) -> WorkspaceMember:
    member = (
        session.query(WorkspaceMember)
        .join(Workspace, Workspace.id == WorkspaceMember.workspace_id)
        .filter(WorkspaceMember.user_id == user.id, Workspace.owner_user_id == user.id)
        .order_by(Workspace.created_at.asc())
        .first()
    )
    if member is not None:
        return member

    now = utc_now()
    short_user_id = user.id.split("-")[0]
    workspace = Workspace(
        name=f"{user.email} workspace" if user.email else f"Workspace {short_user_id}",
        slug=f"personal-{user.id}",
        owner_user_id=user.id,
        status=WorkspaceStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )
    session.add(workspace)
    session.flush()

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role=WorkspaceRole.OWNER,
        created_at=now,
        updated_at=now,
    )
    session.add(member)
    session.add(
        WorkspacePlan(
            workspace_id=workspace.id,
            plan_code="starter",
            billing_status="active",
            max_accounts=10,
            max_jobs_per_day=100,
            max_batch_size=50,
            max_storage_mb=1024,
            max_team_members=1,
            created_at=now,
            updated_at=now,
        )
    )
    session.flush()
    return member


__all__ = [
    "ensure_default_workspace",
    "ensure_personal_workspace",
    "get_or_create_external_user",
    "resolve_workspace_membership",
]
