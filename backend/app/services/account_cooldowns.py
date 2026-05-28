"""Compatibility wrapper.

Canonical owner: app.modules.account_safety.cooldowns
Do not add new behavior here.
"""

from __future__ import annotations

from app.modules.account_safety.cooldowns import (
    active_cooldowns_by_operation,
    batch_active_cooldowns_by_operation,
    batch_latest_succeeded_steps,
    batch_recent_failed_steps,
    cooldown_from_failed_step,
    cooldown_to_dict,
    create_cooldown_from_error,
    ensure_cooldowns_from_recent_failures,
    list_active_account_cooldowns,
    merge_cooldowns,
    product_cooldown_seconds,
    product_cooldowns_by_operation,
    product_cooldowns_from_steps,
    recent_failure_cooldowns_by_operation,
    recent_failure_cooldowns_from_steps,
)

__all__ = [
    "active_cooldowns_by_operation",
    "batch_active_cooldowns_by_operation",
    "batch_latest_succeeded_steps",
    "batch_recent_failed_steps",
    "cooldown_from_failed_step",
    "cooldown_to_dict",
    "create_cooldown_from_error",
    "ensure_cooldowns_from_recent_failures",
    "list_active_account_cooldowns",
    "merge_cooldowns",
    "product_cooldown_seconds",
    "product_cooldowns_by_operation",
    "product_cooldowns_from_steps",
    "recent_failure_cooldowns_by_operation",
    "recent_failure_cooldowns_from_steps",
]
