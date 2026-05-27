from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WorkspaceSafetyPolicy, new_id, utc_now
from app.modules.account_safety.policy_rules import WorkspaceSafetyMode, apply_preset_defaults
from app.services.workspaces import ensure_default_workspace


def get_workspace_safety_policy(
    session: Session,
    *,
    workspace_id: str,
    create_if_missing: bool = False,
) -> WorkspaceSafetyPolicy | None:
    policy = session.execute(
        select(WorkspaceSafetyPolicy).where(WorkspaceSafetyPolicy.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if policy is not None or not create_if_missing:
        return policy
    return create_workspace_safety_policy(session, workspace_id=workspace_id, mode="balanced")


def create_workspace_safety_policy(
    session: Session,
    *,
    workspace_id: str,
    mode: WorkspaceSafetyMode = "balanced",
) -> WorkspaceSafetyPolicy:
    if workspace_id == DEFAULT_LOCAL_WORKSPACE_ID:
        ensure_default_workspace(session)
    values = apply_preset_defaults(mode)
    now = utc_now()
    policy = WorkspaceSafetyPolicy(
        id=new_id(),
        workspace_id=workspace_id,
        created_at=now,
        updated_at=now,
    )
    # Use setattr so explicit None values (e.g. aggressive typing_chars_per_minute)
    # are not silently replaced by column defaults during flush.
    for key, value in values.items():
        setattr(policy, key, value)
    session.add(policy)
    session.flush()
    return policy


def update_workspace_safety_policy(
    session: Session,
    *,
    workspace_id: str,
    values: dict[str, Any],
) -> WorkspaceSafetyPolicy:
    policy = get_workspace_safety_policy(session, workspace_id=workspace_id, create_if_missing=True)
    if policy is None:
        raise RuntimeError("workspace safety policy was not created")

    explicit_values = dict(values)
    update_values: dict[str, Any] = {}
    mode = explicit_values.pop("mode", None)
    if mode is not None:
        update_values.update(apply_preset_defaults(cast(WorkspaceSafetyMode, mode)))
    update_values.update(explicit_values)

    changed_values = {
        key: value
        for key, value in update_values.items()
        if not hasattr(policy, key) or getattr(policy, key) != value
    }
    if changed_values:
        changed_values["updated_at"] = utc_now()

    for key, value in changed_values.items():
        setattr(policy, key, value)
    session.flush()
    return policy


def delete_workspace_safety_policy(session: Session, *, workspace_id: str) -> bool:
    policy = get_workspace_safety_policy(session, workspace_id=workspace_id)
    if policy is None:
        return False
    session.delete(policy)
    session.flush()
    return True


__all__ = [
    "create_workspace_safety_policy",
    "delete_workspace_safety_policy",
    "get_workspace_safety_policy",
    "update_workspace_safety_policy",
]
