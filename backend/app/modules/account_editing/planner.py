from __future__ import annotations

import hashlib
import json
from typing import Any, cast

PROFILE_STEP_TYPES = ("set_name", "set_bio", "set_username", "set_profile_photo", "set_pinned_channel")
WORKFLOW_TYPE = "account_update"
WORKFLOW_VERSION = 1
JOB_PAYLOAD_VERSION = 2


def profile_payload_to_account_update_desired_state(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_account_update_desired_state(
        {
            "profile": {
                "name": payload.get("name"),
                "bio": payload.get("bio"),
                "username": payload.get("username"),
                "photo_asset_id": payload.get("photo_asset_id"),
                "photo_asset_path": payload.get("photo_asset_path"),
                "pinned_channel_ref": payload.get("pinned_channel_ref"),
            },
            "profile_audio": {"action": "keep", "audio_asset_id": None},
            "stories": [],
        }
    )


def normalize_account_update_desired_state(desired_state: dict[str, Any]) -> dict[str, Any]:
    stories = cast(list[dict[str, Any]], desired_state.get("stories") or [])

    profile = cast(dict[str, Any], desired_state.get("profile") or {})
    profile_audio = cast(dict[str, Any], desired_state.get("profile_audio") or {})
    audio_action = profile_audio.get("action") or "keep"
    if audio_action not in {"keep", "add", "remove"}:
        raise ValueError("unsupported profile_audio action")
    if audio_action == "add" and not profile_audio.get("audio_asset_id"):
        raise ValueError("profile_audio audio_asset_id is required")
    normalized_stories = [_normalize_story(index, story) for index, story in enumerate(stories)]

    normalized: dict[str, Any] = {
        "profile": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "username": profile.get("username"),
            "photo_asset_id": profile.get("photo_asset_id"),
            "pinned_channel_ref": profile.get("pinned_channel_ref"),
        },
        "profile_audio": {
            "action": audio_action,
            "audio_asset_id": profile_audio.get("audio_asset_id"),
        },
        "stories": normalized_stories,
    }
    if profile.get("photo_asset_path"):
        normalized["profile"]["photo_asset_path"] = profile.get("photo_asset_path")
    if profile_audio.get("audio_asset_path"):
        normalized["profile_audio"]["audio_asset_path"] = profile_audio.get("audio_asset_path")
    if profile_audio.get("title"):
        normalized["profile_audio"]["title"] = profile_audio.get("title")
    if profile_audio.get("telegram_file_id"):
        normalized["profile_audio"]["telegram_file_id"] = profile_audio.get("telegram_file_id")
    return normalized


def _normalize_story(index: int, story: dict[str, Any]) -> dict[str, Any]:
    action = story.get("action")
    if action not in {"post_image", "post_video"}:
        raise ValueError("unsupported story action")
    if not story.get("asset_id"):
        raise ValueError("story asset_id is required")
    caption = story.get("caption") or None
    if caption and len(caption) > 1024:
        raise ValueError("story caption is too long")
    privacy_preset = story.get("privacy_preset") or "contacts"
    if privacy_preset not in {"contacts", "close_friends", "public"}:
        raise ValueError("unsupported story privacy_preset")
    active_period_seconds = int(story.get("active_period_seconds") or 86400)
    if active_period_seconds != 86400:
        raise ValueError("only 24h story active period is supported before live capability check")
    normalized: dict[str, Any] = {
        "client_id": story.get("client_id") or f"story-{index + 1}",
        "action": action,
        "asset_id": story.get("asset_id"),
        "asset_path": story.get("asset_path"),
        "media_kind": "image" if action == "post_image" else "video",
        "caption": caption,
        "privacy_preset": privacy_preset,
        "active_period_seconds": active_period_seconds,
        "protect_content": bool(story.get("protect_content")),
    }
    return normalized


def account_update_profile_payload(desired_state: dict[str, Any]) -> dict[str, Any]:
    profile = normalize_account_update_desired_state(desired_state)["profile"]
    return {
        "name": profile.get("name"),
        "bio": profile.get("bio"),
        "username": profile.get("username"),
        "photo_asset_id": profile.get("photo_asset_id"),
        "photo_asset_path": profile.get("photo_asset_path"),
        "pinned_channel_ref": profile.get("pinned_channel_ref"),
    }


def canonical_account_update_desired_state(desired_state: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_account_update_desired_state(desired_state)
    profile = normalized["profile"]
    return {
        "profile": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "username": profile.get("username"),
            "photo_asset_id": profile.get("photo_asset_id"),
            "pinned_channel_ref": profile.get("pinned_channel_ref"),
        },
        "profile_audio": normalized["profile_audio"],
        "stories": normalized["stories"],
    }


def compute_account_update_intent_hash(account_id: str, desired_state: dict[str, Any]) -> str:
    material: dict[str, Any] = {
        "account_id": account_id,
        "workflow_type": WORKFLOW_TYPE,
        "workflow_version": WORKFLOW_VERSION,
        "desired_state": canonical_account_update_desired_state(desired_state),
        "job_payload_version": JOB_PAYLOAD_VERSION,
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_account_update_plan(
    desired_state: dict[str, Any],
    *,
    profile_step_types: set[str] | None = None,
) -> dict[str, Any]:
    normalized = normalize_account_update_desired_state(desired_state)
    profile = cast(dict[str, Any], normalized["profile"])
    profile_audio = cast(dict[str, Any], normalized["profile_audio"])
    selected_profile_step_types = (
        set(PROFILE_STEP_TYPES) if profile_step_types is None else profile_step_types
    )
    name = profile.get("name") or ""
    name_parts = name.split(maxsplit=1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    step_payloads: dict[str, dict[str, Any]] = {
        "set_name": {"name": profile.get("name"), "first_name": first_name, "last_name": last_name},
        "set_bio": {"bio": profile.get("bio")},
        "set_username": {"username": profile.get("username")},
        "set_profile_photo": {
            "photo_asset_id": profile.get("photo_asset_id"),
            "asset_path": profile.get("photo_asset_path"),
        },
        "set_pinned_channel": {"pinned_channel_ref": profile.get("pinned_channel_ref")},
    }
    capability_keys = {
        "set_name": "profile_text",
        "set_bio": "profile_text",
        "set_username": "profile_text",
        "set_profile_photo": "profile_photo",
        "set_pinned_channel": "profile_text",
    }
    compensation_policies = {
        "set_name": "restore_previous_value",
        "set_bio": "restore_previous_value",
        "set_username": "manual_only",
        "set_profile_photo": "manual_only",
        "set_pinned_channel": "manual_only",
    }
    steps: list[dict[str, Any]] = []
    for step_type in PROFILE_STEP_TYPES:
        if step_type not in selected_profile_step_types:
            continue
        steps.append(
            {
                "step_key": step_type,
                "step_type": step_type,
                "order": len(steps) + 1,
                "required": True,
                "capability_key": capability_keys[step_type],
                "retry_policy": "standard",
                "compensation_policy": compensation_policies[step_type],
                "idempotency_class": "profile_field_replace",
                "payload": step_payloads[step_type],
            }
        )

    audio_action = profile_audio.get("action")
    if audio_action == "add":
        steps.extend(
            [
                {
                    "step_key": "upload_profile_audio",
                    "step_type": "upload_profile_audio",
                    "order": len(steps) + 1,
                    "required": True,
                    "capability_key": "profile_audio",
                    "retry_policy": "media_upload",
                    "compensation_policy": "manual_only",
                    "idempotency_class": "media_upload",
                    "payload": {
                        "audio_asset_id": profile_audio.get("audio_asset_id"),
                        "asset_path": profile_audio.get("audio_asset_path"),
                        "title": profile_audio.get("title"),
                    },
                },
                {
                    "step_key": "add_profile_audio",
                    "step_type": "add_profile_audio",
                    "order": len(steps) + 2,
                    "required": True,
                    "capability_key": "profile_audio",
                    "retry_policy": "standard",
                    "compensation_policy": "remove_profile_audio",
                    "idempotency_class": "profile_audio_replace",
                    "payload": {
                        "audio_asset_id": profile_audio.get("audio_asset_id"),
                    },
                },
            ]
        )
    elif audio_action == "remove":
        steps.append(
            {
                "step_key": "remove_profile_audio",
                "step_type": "remove_profile_audio",
                "order": len(steps) + 1,
                "required": True,
                "capability_key": "profile_audio",
                "retry_policy": "standard",
                "compensation_policy": "manual_only",
                "idempotency_class": "profile_audio_remove",
                "payload": {"telegram_file_id": profile_audio.get("telegram_file_id")},
            }
        )

    for story_index, story in enumerate(cast(list[dict[str, Any]], normalized["stories"]), start=1):
        prefix = f"story_{story_index}"
        base_payload: dict[str, Any] = {
            "client_id": story["client_id"],
            "asset_id": story["asset_id"],
            "asset_path": story.get("asset_path"),
            "media_kind": story["media_kind"],
            "caption": story.get("caption"),
            "privacy_preset": story["privacy_preset"],
            "active_period_seconds": story["active_period_seconds"],
            "protect_content": story["protect_content"],
        }
        steps.extend(
            [
                {
                    "step_key": f"{prefix}_validate_capabilities",
                    "step_type": "validate_story_capabilities",
                    "order": len(steps) + 1,
                    "required": True,
                    "capability_key": f"stories_{story['media_kind']}",
                    "retry_policy": "none",
                    "compensation_policy": "manual_only",
                    "idempotency_class": "story_preflight",
                    "payload": base_payload,
                },
                {
                    "step_key": f"{prefix}_prepare_media",
                    "step_type": "prepare_story_media",
                    "order": len(steps) + 2,
                    "required": True,
                    "capability_key": f"stories_{story['media_kind']}",
                    "retry_policy": "media_upload",
                    "compensation_policy": "manual_only",
                    "idempotency_class": "story_media_prepare",
                    "payload": base_payload,
                },
                {
                    "step_key": f"{prefix}_post",
                    "step_type": "post_story_image"
                    if story["media_kind"] == "image"
                    else "post_story_video",
                    "order": len(steps) + 3,
                    "required": True,
                    "capability_key": f"stories_{story['media_kind']}",
                    "retry_policy": "standard",
                    "compensation_policy": "manual_only",
                    "idempotency_class": "story_publish",
                    "payload": base_payload,
                },
            ]
        )

    return {
        "workflow_type": WORKFLOW_TYPE,
        "workflow_version": WORKFLOW_VERSION,
        "plan_version": WORKFLOW_VERSION,
        "job_payload_version": JOB_PAYLOAD_VERSION,
        "steps": steps,
    }


def default_capability_snapshot() -> dict[str, str]:
    return {
        "profile_text": "true",
        "profile_photo": "true",
        "profile_audio": "unknown",
        "stories_image": "unknown",
        "stories_video": "unknown",
        "stories_caption_entities": "unknown",
    }
