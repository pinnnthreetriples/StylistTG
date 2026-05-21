from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WorkspaceSafetyPolicy, new_id, utc_now
from app.services.workspaces import ensure_default_workspace

WorkspaceSafetyMode = Literal["conservative", "balanced", "aggressive"]
PUBLIC_POLICY_FIELDS = (
    "mode",
    "delay_multiplier",
    "typing_chars_per_minute_min",
    "typing_chars_per_minute_max",
    "profile_view_probability",
    "scroll_probability",
    "typo_probability",
    "message_deletion_probability",
    "quiet_hours_local_start",
    "quiet_hours_local_end",
    "require_warmup_before_commenting",
    "min_warmup_days",
    "require_healthy_proxy",
    "min_account_age_hours",
    "auto_pause_on_flood_wait_count",
    "auto_pause_on_deleted_comments_count",
    "quarantine_hours_on_flood_wait",
)
_MISSING = object()


@dataclass(frozen=True)
class WorkspaceSafetyPolicyDefaults:
    delay_multiplier: float
    typing_chars_per_minute_min: int | None
    typing_chars_per_minute_max: int | None
    profile_view_probability: float
    scroll_probability: float
    typo_probability: float
    message_deletion_probability: float
    quiet_hours_local_start: int | None
    quiet_hours_local_end: int | None
    require_warmup_before_commenting: bool
    min_warmup_days: int
    require_healthy_proxy: bool
    min_account_age_hours: int
    auto_pause_on_flood_wait_count: int
    auto_pause_on_deleted_comments_count: int
    quarantine_hours_on_flood_wait: int = 24

    def as_update(self, *, mode: WorkspaceSafetyMode) -> dict[str, Any]:
        return {"mode": mode, **self.__dict__}


PRESET_DEFAULTS: dict[WorkspaceSafetyMode, WorkspaceSafetyPolicyDefaults] = {
    "conservative": WorkspaceSafetyPolicyDefaults(
        delay_multiplier=1.5,
        typing_chars_per_minute_min=40,
        typing_chars_per_minute_max=60,
        profile_view_probability=0.9,
        scroll_probability=0.5,
        typo_probability=0.08,
        message_deletion_probability=0.03,
        quiet_hours_local_start=60,
        quiet_hours_local_end=420,
        require_warmup_before_commenting=True,
        min_warmup_days=7,
        require_healthy_proxy=True,
        min_account_age_hours=72,
        auto_pause_on_flood_wait_count=1,
        auto_pause_on_deleted_comments_count=2,
    ),
    "balanced": WorkspaceSafetyPolicyDefaults(
        delay_multiplier=1.0,
        typing_chars_per_minute_min=100,
        typing_chars_per_minute_max=150,
        profile_view_probability=0.7,
        scroll_probability=0.3,
        typo_probability=0.05,
        message_deletion_probability=0.02,
        quiet_hours_local_start=120,
        quiet_hours_local_end=360,
        require_warmup_before_commenting=True,
        min_warmup_days=3,
        require_healthy_proxy=True,
        min_account_age_hours=24,
        auto_pause_on_flood_wait_count=3,
        auto_pause_on_deleted_comments_count=5,
    ),
    "aggressive": WorkspaceSafetyPolicyDefaults(
        delay_multiplier=0.7,
        typing_chars_per_minute_min=None,
        typing_chars_per_minute_max=None,
        profile_view_probability=0.3,
        scroll_probability=0.0,
        typo_probability=0.02,
        message_deletion_probability=0.01,
        quiet_hours_local_start=None,
        quiet_hours_local_end=None,
        require_warmup_before_commenting=False,
        min_warmup_days=1,
        require_healthy_proxy=False,
        min_account_age_hours=0,
        auto_pause_on_flood_wait_count=5,
        auto_pause_on_deleted_comments_count=10,
    ),
}


def apply_preset_defaults(mode: WorkspaceSafetyMode) -> dict[str, Any]:
    return PRESET_DEFAULTS[mode].as_update(mode=mode)


def policy_public_snapshot(policy: WorkspaceSafetyPolicy | Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: value
        for field in PUBLIC_POLICY_FIELDS
        if (value := _policy_value(policy, field)) is not _MISSING
    }


def compute_diff(
    old: WorkspaceSafetyPolicy | Mapping[str, Any],
    new: WorkspaceSafetyPolicy | Mapping[str, Any],
) -> dict[str, Any]:
    old_values = policy_public_snapshot(old)
    new_values = policy_public_snapshot(new)
    changed_fields = [
        field
        for field in PUBLIC_POLICY_FIELDS
        if field in old_values and field in new_values and old_values[field] != new_values[field]
    ]
    return {
        "changed_fields": changed_fields,
        "old": {field: old_values[field] for field in changed_fields},
        "new": {field: new_values[field] for field in changed_fields},
    }


def _policy_value(policy: WorkspaceSafetyPolicy | Mapping[str, Any], field: str) -> Any:
    if isinstance(policy, Mapping):
        return policy.get(field, _MISSING)
    return getattr(policy, field, _MISSING)


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
        update_values.update(apply_preset_defaults(mode))
    update_values.update(explicit_values)

    changed_values = {
        key: value
        for key, value in update_values.items()
        if _policy_value(policy, key) is _MISSING or getattr(policy, key) != value
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
    "PRESET_DEFAULTS",
    "PUBLIC_POLICY_FIELDS",
    "apply_preset_defaults",
    "compute_diff",
    "create_workspace_safety_policy",
    "delete_workspace_safety_policy",
    "get_workspace_safety_policy",
    "policy_public_snapshot",
    "update_workspace_safety_policy",
]
