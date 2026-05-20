from __future__ import annotations

from typing import Any

SUPPORTED_ACCOUNT_UPDATE_STEP_TYPES = {
    "set_name",
    "set_bio",
    "set_username",
    "set_profile_photo",
    "set_pinned_channel",
    "upload_profile_audio",
    "add_profile_audio",
    "remove_profile_audio",
    "validate_story_capabilities",
    "prepare_story_media",
    "post_story_image",
    "post_story_video",
}


def validate_account_update_plan_steps(plan_json_snapshot: dict[str, Any]) -> None:
    for step in plan_json_snapshot.get("steps", []):
        step_type = step.get("step_type")
        if step_type not in SUPPORTED_ACCOUNT_UPDATE_STEP_TYPES:
            raise ValueError(f"unsupported account update step type: {step_type}")
