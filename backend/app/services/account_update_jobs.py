from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import AccountState, AssetKind, AssetStatus, Job, JobState, utc_now
from app.services.account_update_plan import (
    account_update_profile_payload,
    build_account_update_plan,
    compute_account_update_intent_hash,
    default_capability_snapshot,
    normalize_account_update_desired_state,
)
from app.services.accounts import get_account
from app.services.auth import is_account_hard_stopped
from app.services.assets import PROFILE_AUDIO_EXECUTION_MIMES, get_asset
from app.services.execution_policy import ExecutionUsableAdapter, ensure_execution_usable
from app.services.jobs import (
    find_active_duplicate_job,
    is_profile_job_cooldown_active,
    normalize_profile_payload,
)
from app.services.profile_photo_state import latest_applied_profile_photo_asset_id
from app.services.step_registry import validate_account_update_plan_steps


def build_account_update_preview(session: Session, *, account_id: str, desired_state: dict) -> dict:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")

    requested_profile_fields = _requested_profile_fields(desired_state)
    desired_state = _normalize_with_profile_assets(session, account_id=account_id, desired_state=desired_state)
    intent_hash = compute_account_update_intent_hash(account_id, desired_state)
    duplicate = find_active_duplicate_job(session, account_id, intent_hash)
    plan = build_account_update_plan(
        desired_state,
        profile_step_types=_changed_profile_step_types(
            session,
            account=account,
            desired_state=desired_state,
            requested_profile_fields=requested_profile_fields,
        ),
    )
    validate_account_update_plan_steps(plan)

    blocking_errors: list[str] = []
    warnings: list[str] = []
    if is_account_hard_stopped(account):
        blocking_errors.append("account requires manual intervention")
    if account.account_state != AccountState.EXECUTION_USABLE:
        blocking_errors.append("account is not execution_usable")
    if is_profile_job_cooldown_active(session, account_id):
        blocking_errors.append("profile job cooldown active")
    if desired_state.get("stories") and not settings.stories_enabled:
        blocking_errors.append("stories are disabled")
    if desired_state.get("stories") and _stories_live_execution_blocked(settings):
        blocking_errors.append("stories live TDLib execution is not enabled")

    return {
        "can_create_job": not blocking_errors,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "normalized_payload": account_update_profile_payload(desired_state),
        "desired_state_normalized": desired_state,
        "execution_intent_hash": intent_hash,
        "workflow_type": "account_update",
        "workflow_version": 1,
        "capability_snapshot": default_capability_snapshot(),
        "plan_json_snapshot": plan,
        "steps": plan["steps"],
        "requires_execution_usable": True,
        "dedup_would_block": duplicate is not None,
        "dedup_blocked_by_job_id": duplicate.id if duplicate else None,
    }


def create_account_update_job(
    session: Session,
    *,
    account_id: str,
    desired_state: dict,
    execution_adapter: ExecutionUsableAdapter | None = None,
    config: Settings = settings,
) -> Job:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")
    if is_account_hard_stopped(account):
        raise ValueError("account requires manual intervention")

    if execution_adapter is not None:
        policy = ensure_execution_usable(session, account_id, adapter=execution_adapter)
        if not policy.ok or policy.account.account_state != AccountState.EXECUTION_USABLE:
            raise ValueError("account is not execution_usable")

    if is_profile_job_cooldown_active(session, account_id, config=config):
        raise ValueError("profile job cooldown active")
    if desired_state.get("stories") and not config.stories_enabled:
        raise ValueError("stories are disabled")
    if desired_state.get("stories") and _stories_live_execution_blocked(config):
        raise ValueError("stories live TDLib execution is not enabled")

    requested_profile_fields = _requested_profile_fields(desired_state)
    desired_state = _normalize_with_profile_assets(session, account_id=account_id, desired_state=desired_state)
    plan = build_account_update_plan(
        desired_state,
        profile_step_types=_changed_profile_step_types(
            session,
            account=account,
            desired_state=desired_state,
            requested_profile_fields=requested_profile_fields,
        ),
    )
    validate_account_update_plan_steps(plan)
    intent_hash = compute_account_update_intent_hash(account_id, desired_state)
    duplicate = find_active_duplicate_job(session, account_id, intent_hash)
    state = JobState.DEDUP_BLOCKED if duplicate else JobState.QUEUED
    job = Job(
        account_id=account_id,
        job_state=state,
        workflow_type="account_update",
        workflow_version=1,
        execution_intent_hash=intent_hash,
        job_payload_version=2,
        payload_json=account_update_profile_payload(desired_state),
        desired_state_json=desired_state,
        capability_snapshot_json=default_capability_snapshot(),
        plan_json_snapshot=plan,
        dedup_blocked_by_job_id=duplicate.id if duplicate else None,
        queued_at=utc_now() if not duplicate else None,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    log_event(
        "account_update_job_created",
        job_id=job.id,
        account_id=account_id,
        state=job.job_state,
        intent_hash=intent_hash[:12],
        steps=len(job.plan_json_snapshot.get("steps", [])),
        dedup=duplicate.id if duplicate else None,
    )
    return job


def _normalize_with_profile_assets(session: Session, *, account_id: str, desired_state: dict) -> dict:
    desired_state = normalize_account_update_desired_state(desired_state)
    profile_payload = normalize_profile_payload(session, account_update_profile_payload(desired_state))
    desired_state["profile"]["photo_asset_path"] = profile_payload.get("photo_asset_path")
    _validate_profile_audio_asset(session, account_id=account_id, desired_state=desired_state)
    _validate_story_assets(session, desired_state)
    return desired_state


def _validate_profile_audio_asset(session: Session, *, account_id: str, desired_state: dict) -> None:
    profile_audio = desired_state.get("profile_audio") or {}
    if profile_audio.get("action") == "remove":
        account = get_account(session, account_id)
        if account and account.profile_audio_state:
            profile_audio["telegram_file_id"] = account.profile_audio_state.telegram_file_id
        return
    if profile_audio.get("action") != "add":
        return
    asset_id = profile_audio.get("audio_asset_id")
    asset = get_asset(session, asset_id)
    if asset is None:
        raise ValueError("audio asset not found")
    if asset.kind != AssetKind.PROFILE_AUDIO:
        raise ValueError("asset kind is not profile_audio")
    if asset.status != AssetStatus.NORMALIZED:
        raise ValueError("asset is not ready for profile audio execution")
    if asset.mime not in PROFILE_AUDIO_EXECUTION_MIMES:
        raise ValueError("profile audio must be MP3 or M4A")
    profile_audio["audio_asset_path"] = str((settings.local_storage_path / asset.normalized_path).resolve())
    profile_audio["title"] = _profile_audio_title(asset.original_filename)


def _profile_audio_title(filename: str | None) -> str:
    if not filename:
        return ""
    title = Path(filename).stem.strip()
    return title[:64]


def _validate_story_assets(session: Session, desired_state: dict) -> None:
    for story in desired_state.get("stories") or []:
        asset = get_asset(session, story.get("asset_id"))
        if asset is None:
            raise ValueError("story asset not found")
        expected_kind = AssetKind.STORY_IMAGE if story.get("action") == "post_image" else AssetKind.STORY_VIDEO
        if asset.kind != expected_kind:
            raise ValueError(f"asset kind is not {expected_kind}")
        if asset.status != AssetStatus.NORMALIZED:
            raise ValueError("asset is not ready for story execution")
        story["asset_path"] = str((settings.local_storage_path / asset.normalized_path).resolve())


def _stories_live_execution_blocked(config: Settings) -> bool:
    return config.profile_execution_adapter == "tdlib" and not config.stories_tdlib_live_enabled


def _requested_profile_fields(desired_state: dict) -> set[str]:
    profile = desired_state.get("profile")
    if not isinstance(profile, dict):
        return set()
    return set(profile)


def _changed_profile_step_types(
    session: Session,
    *,
    account,
    desired_state: dict,
    requested_profile_fields: set[str],
) -> set[str]:
    profile = desired_state.get("profile") or {}
    profile_state = account.profile_state
    steps: set[str] = set()

    if "name" in requested_profile_fields:
        current_name = " ".join(
            part for part in [profile_state.first_name if profile_state else None, profile_state.last_name if profile_state else None]
            if part
        )
        if (profile.get("name") or "") != current_name:
            steps.add("set_name")
    if "bio" in requested_profile_fields and (profile.get("bio") or "") != ((profile_state.bio if profile_state else None) or ""):
        steps.add("set_bio")
    if "username" in requested_profile_fields and (profile.get("username") or "") != (
        (profile_state.username if profile_state else None) or ""
    ):
        steps.add("set_username")
    if "photo_asset_id" in requested_profile_fields:
        desired_photo_asset_id = profile.get("photo_asset_id")
        current_photo_asset_id = latest_applied_profile_photo_asset_id(session, account.id)
        if desired_photo_asset_id and desired_photo_asset_id != current_photo_asset_id:
            steps.add("set_profile_photo")

    return steps
