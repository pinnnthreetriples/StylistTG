from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMember, WorkspacePlan, WorkspaceRole, WorkspaceStatus, utc_now


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
