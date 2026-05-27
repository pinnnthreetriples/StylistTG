"""Compatibility facade for workspace safety policy use cases."""

from __future__ import annotations

from app.modules.account_safety.policy_repository import (
    create_workspace_safety_policy,
    delete_workspace_safety_policy,
    get_workspace_safety_policy,
    update_workspace_safety_policy,
)
from app.modules.account_safety.policy_rules import (
    DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD,
    PRESET_DEFAULTS,
    PUBLIC_POLICY_FIELDS,
    WorkspaceSafetyMode,
    WorkspaceSafetyPolicyDefaults,
    apply_preset_defaults,
    compute_diff,
    get_consecutive_failure_threshold,
    policy_public_snapshot,
)

__all__ = [
    "DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD",
    "PRESET_DEFAULTS",
    "PUBLIC_POLICY_FIELDS",
    "WorkspaceSafetyMode",
    "WorkspaceSafetyPolicyDefaults",
    "apply_preset_defaults",
    "compute_diff",
    "create_workspace_safety_policy",
    "delete_workspace_safety_policy",
    "get_consecutive_failure_threshold",
    "get_workspace_safety_policy",
    "policy_public_snapshot",
    "update_workspace_safety_policy",
]
