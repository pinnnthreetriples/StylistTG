from __future__ import annotations

# pyright: reportPrivateUsage=false, reportUnusedFunction=false

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from app.adapters.tdlib_profile_common import _dict_or_empty
from app.models import JobState, StepStatus


def split_name(full_name: str | None) -> tuple[str, str]:
    normalized = (full_name or "").strip()
    if not normalized:
        return "", ""
    parts = normalized.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _query_set_name(payload: dict[str, Any]) -> dict[str, Any]:
    first_name = payload.get("first_name")
    last_name = payload.get("last_name")
    if first_name is None and last_name is None:
        first_name, last_name = split_name(payload.get("name"))
    return {"@type": "setName", "first_name": first_name or "", "last_name": last_name or ""}


def _query_set_bio(payload: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "setBio", "bio": payload.get("bio") or ""}


def _query_set_username(payload: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "setUsername", "username": payload.get("username") or ""}


def _query_set_pinned_channel(payload: dict[str, Any]) -> dict[str, Any]:
    channel_ref = payload.get("pinned_channel_ref") or ""
    if not channel_ref:
        return {"@type": "setPersonalChat", "chat_id": 0}
    if channel_ref.startswith("@"):
        return {"@type": "searchPublicChat", "username": channel_ref.lstrip("@")}
    if channel_ref.lstrip("-").isdigit():
        return {"@type": "setPersonalChat", "chat_id": int(channel_ref)}
    return {"@type": "setPersonalChat", "chat_id": 0}


def _query_set_profile_photo(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "setProfilePhoto",
        "photo": {
            "@type": "inputChatPhotoStatic",
            "photo": {
                "@type": "inputFileLocal",
                "path": payload["asset_path"],
            },
        },
        "is_public": False,
    }


def _query_add_profile_audio(payload: dict[str, Any]) -> dict[str, Any]:
    file_id = payload.get("telegram_file_id")
    if file_id is None:
        raise ValueError("telegram_file_id is required for add_profile_audio")
    return {"@type": "addProfileAudio", "file_id": int(file_id)}


def _query_remove_profile_audio(payload: dict[str, Any]) -> dict[str, Any]:
    file_id = payload.get("telegram_file_id")
    if file_id is None:
        return {"@type": "getMe"}
    return {"@type": "removeProfileAudio", "file_id": int(file_id)}


def _query_get_me(_payload: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "getMe"}


_STEP_QUERY_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "set_name": _query_set_name,
    "set_bio": _query_set_bio,
    "set_username": _query_set_username,
    "set_pinned_channel": _query_set_pinned_channel,
    "set_profile_photo": _query_set_profile_photo,
    "add_profile_audio": _query_add_profile_audio,
    "remove_profile_audio": _query_remove_profile_audio,
    "validate_story_capabilities": _query_get_me,
    "prepare_story_media": _query_get_me,
}


def map_step_to_tdlib_query(step: dict[str, Any]) -> dict[str, Any]:
    step_type = step["step_type"]
    payload = step["payload"]
    query_builder = _STEP_QUERY_BUILDERS.get(step_type)
    if query_builder is not None:
        return query_builder(payload)
    raise ValueError(f"Unsupported profile step type: {step_type}")


def verify_username_result(desired_username: str, me_response: dict[str, Any]) -> dict[str, Any]:
    usernames = _dict_or_empty(me_response.get("usernames"))
    active_value = usernames.get("active_usernames")
    active = cast(list[Any], active_value) if isinstance(active_value, list) else []
    editable = usernames.get("editable_username")
    matched = desired_username == editable or desired_username in active
    if matched:
        return {
            "status": StepStatus.SUCCEEDED,
            "verification_attempted": True,
            "verification_result": {"editable_username": editable, "active_usernames": active},
            "uncertain_reason": None,
        }
    return {
        "status": StepStatus.UNCERTAIN,
        "verification_attempted": True,
        "verification_result": {"editable_username": editable, "active_usernames": active},
        "uncertain_reason": "username_verify_mismatch",
        "result_payload": {"desired_username": desired_username},
    }


def classify_step_outcome(step_type: str, outcome: str) -> StepStatus:
    if outcome == "uncertain":
        return StepStatus.UNCERTAIN
    if outcome == "failed":
        return StepStatus.FAILED
    return StepStatus.SUCCEEDED


def classify_job_outcome(step_results: list[dict[str, Any]]) -> JobState:
    statuses = {result["status"] for result in step_results}
    if StepStatus.FAILED in statuses:
        return JobState.FAILED
    if any(
        result["status"] == StepStatus.UNCERTAIN and result["step_type"] == "set_username"
        for result in step_results
    ):
        return JobState.MANUAL_INTERVENTION_NEEDED
    if StepStatus.UNCERTAIN in statuses:
        return JobState.PARTIALLY_COMPLETED
    return JobState.COMPLETED


@dataclass
class _ProfileAudioState:
    file_id: int | None = None
    temp_message: dict[str, Any] | None = None
    title: str | None = None


@dataclass(frozen=True)
class _StepExecutionResult:
    events: list[dict[str, Any]]
    stop_runtime: bool = False


def _with_uploaded_profile_audio_id(
    step: dict[str, Any], audio_state: _ProfileAudioState
) -> dict[str, Any]:
    if step["step_type"] != "add_profile_audio" or audio_state.file_id is None:
        return step
    return {
        **step,
        "payload": {
            **step["payload"],
            "telegram_file_id": audio_state.file_id,
        },
    }


def _story_post_step_result(
    story_post: dict[str, Any], event: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": True,
                "verification_result": {
                    "telegram_story_id": story_post["telegram_story_id"],
                    "status": story_post["status"],
                },
                "result_payload": {"story_post": story_post},
            }
        ]
    )


def _profile_audio_upload_step_result(
    step: dict[str, Any],
    event: dict[str, Any],
    uploaded_file: dict[str, Any],
    file_id: int,
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {
                    "audio_asset_id": step["payload"].get("audio_asset_id"),
                    "telegram_file_id": str(file_id),
                    "temporary_message_id": str(uploaded_file.get("message_id") or ""),
                },
            }
        ]
    )


def _failed_pinned_channel_step_result(
    event: dict[str, Any], pinned_result: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_failed",
                **event,
                "error_code": pinned_result["error_code"],
                "error_class": "PinnedChannelResolutionError",
                "result_payload": {
                    "message": pinned_result["error_message"],
                },
            },
            {
                "event": "runtime_failed",
                "error_class": "PinnedChannelResolutionError",
                "error_code": pinned_result["error_code"],
            },
        ],
        stop_runtime=True,
    )


def _applied_step_result(event: dict[str, Any], step: dict[str, Any]) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {"applied": step["payload"]},
            }
        ]
    )


def _profile_audio_add_step_result(
    step: dict[str, Any], event: dict[str, Any], audio_state: _ProfileAudioState
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {
                    "profile_audio": {
                        "source_asset_id": step["payload"].get("audio_asset_id"),
                        "telegram_file_id": str(audio_state.file_id),
                        "title": audio_state.title,
                        "performer": None,
                        "duration_seconds": None,
                        "mime": None,
                    }
                },
            }
        ]
    )


def _profile_audio_remove_step_result(event: dict[str, Any]) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {"profile_audio_removed": True},
            }
        ]
    )


def _uncertain_username_step_result(
    event: dict[str, Any], verification: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_uncertain",
                **event,
                "verification_attempted": True,
                "verification_result": verification["verification_result"],
                "uncertain_reason": verification["uncertain_reason"],
                "result_payload": verification["result_payload"],
            },
            {"event": "runtime_closed"},
        ],
        stop_runtime=True,
    )


def _username_succeeded_step_result(
    event: dict[str, Any], step: dict[str, Any], verification: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": True,
                "verification_result": verification["verification_result"],
                "result_payload": {"applied": step["payload"]},
            }
        ]
    )


def _failed_profile_step_result(exc: Exception, event: dict[str, Any]) -> _StepExecutionResult:
    error_code = getattr(exc, "error_code", "tdlib_profile_step_failed")
    return _StepExecutionResult(
        events=[
            {
                "event": "step_failed",
                **event,
                "error_code": error_code,
                "error_class": exc.__class__.__name__,
                "result_payload": {"message": str(exc)},
            },
            {
                "event": "runtime_failed",
                "error_class": exc.__class__.__name__,
                "error_code": error_code,
            },
        ],
        stop_runtime=True,
    )
