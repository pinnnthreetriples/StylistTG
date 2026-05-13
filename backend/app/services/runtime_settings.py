from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import RuntimeSetting

AUTH_RUNTIME_MODE_KEY = "auth_runtime_mode"
EXECUTION_POLICY_KEY = "execution_policy"

EXECUTION_POLICY_FIELDS = (
    "profile_job_cooldown_seconds",
    "profile_update_cooldown_seconds",
    "username_cooldown_seconds",
    "profile_photo_cooldown_seconds",
    "profile_music_cooldown_seconds",
    "story_post_cooldown_seconds",
    "story_delete_cooldown_seconds",
    "unknown_capability_policy",
    "recent_failure_policy",
    "fresh_validity_required",
    "fresh_validity_max_age_minutes",
    "manual_hard_blocker_override_enabled",
)


def get_auth_runtime_mode(
    session: Session, *, config: Settings = settings
) -> dict[str, bool]:
    values = _get_values(session, AUTH_RUNTIME_MODE_KEY)
    return {
        "tdlib_use_test_dc": bool(
            values.get("tdlib_use_test_dc", config.tdlib_use_test_dc)
        ),
        "tdlib_production_auth_enabled": bool(
            values.get(
                "tdlib_production_auth_enabled",
                config.tdlib_production_auth_enabled,
            )
        ),
    }


def update_auth_runtime_mode(
    session: Session, *, tdlib_use_test_dc: bool
) -> dict[str, bool]:
    values = {
        "tdlib_use_test_dc": tdlib_use_test_dc,
        "tdlib_production_auth_enabled": not tdlib_use_test_dc,
    }
    _set_values(session, AUTH_RUNTIME_MODE_KEY, values)
    return values


def auth_runtime_settings(session: Session, *, config: Settings = settings) -> Settings:
    values = get_auth_runtime_mode(session, config=config)
    return config.model_copy(update=values)


def get_execution_policy(session: Session, *, config: Settings = settings) -> dict[str, Any]:
    values = _get_values(session, EXECUTION_POLICY_KEY)
    return {field: values.get(field, getattr(config, field)) for field in EXECUTION_POLICY_FIELDS}


def update_execution_policy(
    session: Session, values: dict[str, Any], *, config: Settings = settings
) -> dict[str, Any]:
    current = _get_values(session, EXECUTION_POLICY_KEY)
    current.update(values)
    _set_values(session, EXECUTION_POLICY_KEY, current)
    return get_execution_policy(session, config=config)


def execution_policy_settings(session: Session, *, config: Settings = settings) -> Settings:
    return config.model_copy(update=get_execution_policy(session, config=config))


def _get_values(session: Session, key: str) -> dict[str, Any]:
    row = session.get(RuntimeSetting, key)
    if row is None:
        return {}
    return dict(row.value_json)


def _set_values(session: Session, key: str, values: dict[str, Any]) -> None:
    row = session.get(RuntimeSetting, key)
    if row is None:
        row = RuntimeSetting(key=key, value_json=values)
        session.add(row)
    else:
        row.value_json = values
    session.commit()
