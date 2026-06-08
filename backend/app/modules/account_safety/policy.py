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
    DEPRECATED_BEHAVIOR_POLICY_FIELDS,
    PRESET_DEFAULTS,
    PUBLIC_POLICY_FIELDS,
    WorkspaceSafetyMode,
    WorkspaceSafetyPolicyDefaults,
    apply_preset_defaults,
    compute_diff,
    disabled_policy_overlay,
    get_consecutive_failure_threshold,
    is_workspace_safety_policy_temporarily_disabled,
    policy_public_snapshot,
)

__all__ = [
    "DEFAULT_CONSECUTIVE_FAILURE_THRESHOLD",
    "DEPRECATED_BEHAVIOR_POLICY_FIELDS",
    "PRESET_DEFAULTS",
    "PUBLIC_POLICY_FIELDS",
    "WorkspaceSafetyMode",
    "WorkspaceSafetyPolicyDefaults",
    "apply_preset_defaults",
    "compute_diff",
    "create_workspace_safety_policy",
    "delete_workspace_safety_policy",
    "disabled_policy_overlay",
    "get_consecutive_failure_threshold",
    "get_workspace_safety_policy",
    "is_workspace_safety_policy_temporarily_disabled",
    "policy_public_snapshot",
    "update_workspace_safety_policy",
]
