from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol, cast

from app.models import AccountState

ProfileEvent = dict[str, Any]
ProfilePayload = dict[str, Any]
ProfileStep = dict[str, Any]


def _result_remove_profile_audio(_payload: ProfilePayload, _ctx: dict[str, Any]) -> ProfilePayload:
    return {"profile_audio_removed": True}


def _result_mock_applied(payload: ProfilePayload, _ctx: dict[str, Any]) -> ProfilePayload:
    return {"mock": True, "applied": payload}


def _result_upload_profile_audio(payload: ProfilePayload, ctx: dict[str, Any]) -> ProfilePayload:
    audio_asset_id = payload.get("audio_asset_id")
    uploaded_id = f"mock-file-{audio_asset_id}"
    ctx["uploaded_audio_file_id"] = uploaded_id
    return {"audio_asset_id": audio_asset_id, "telegram_file_id": uploaded_id}


def _result_add_profile_audio(payload: ProfilePayload, ctx: dict[str, Any]) -> ProfilePayload:
    audio_asset_id = payload.get("audio_asset_id")
    telegram_file_id = ctx.get("uploaded_audio_file_id") or f"mock-file-{audio_asset_id}"
    return {
        "profile_audio": {
            "source_asset_id": audio_asset_id,
            "telegram_file_id": telegram_file_id,
            "title": None,
            "performer": None,
            "duration_seconds": None,
            "mime": None,
        }
    }


# Mapping of step_type → builder for the `result_payload` of a `step_succeeded`
# event with default verification (attempted=False). Centralizing here keeps
# the per-step branches in `execute()` to early-exit cases only.
_DEFAULT_VERIFICATION_RESULTS: dict[
    str, Callable[[ProfilePayload, dict[str, Any]], ProfilePayload]
] = {
    "upload_profile_audio": _result_upload_profile_audio,
    "add_profile_audio": _result_add_profile_audio,
    "remove_profile_audio": _result_remove_profile_audio,
    "validate_story_capabilities": _result_mock_applied,
    "prepare_story_media": _result_mock_applied,
}


def _post_story_result(payload: ProfilePayload, step_type: str) -> ProfilePayload:
    media_kind = "image" if step_type == "post_story_image" else "video"
    story_id = f"mock-story-{payload.get('client_id')}"
    return {
        "story_post": {
            "status": "posted",
            "telegram_story_id": story_id,
            "temporary_story_id": story_id,
            "media_kind": media_kind,
            "asset_id": payload.get("asset_id"),
            "caption": payload.get("caption"),
            "privacy_preset": payload.get("privacy_preset"),
            "active_period_seconds": payload.get("active_period_seconds"),
            "protect_content": payload.get("protect_content"),
        }
    }


class ProfileExecutionAdapter(Protocol):
    def execute(
        self, account_id: str, plan_json_snapshot: ProfilePayload, payload_json: ProfilePayload
    ) -> Iterator[ProfileEvent]:
        """Yield structured execution events for a profile job."""
        raise NotImplementedError


class MockProfileExecutionAdapter:
    def inspect_runtime(self, account_id: str) -> ProfilePayload:
        return {
            "ok": True,
            "account_state": AccountState.EXECUTION_USABLE,
            "runtime_health": "ready",
            "telegram_user_id": "mock-user",
            "error": None,
        }

    def execute(
        self, account_id: str, plan_json_snapshot: ProfilePayload, payload_json: ProfilePayload
    ) -> Iterator[ProfileEvent]:
        yield {"event": "runtime_started"}
        fail_step = payload_json.get("mock_fail_step")
        crash_step = payload_json.get("mock_crash_after_step_started")
        username_verify = payload_json.get("mock_username_verify")
        ctx: dict[str, Any] = {"uploaded_audio_file_id": None}

        for step in cast(list[ProfileStep], plan_json_snapshot["steps"]):
            payload = cast(ProfilePayload, step["payload"])
            step_type = str(step["step_type"])
            event: ProfileEvent = {
                "step_key": step["step_key"],
                "step_type": step_type,
            }
            yield {"event": "step_started", **event}

            if crash_step == step_type:
                raise SystemExit(2)

            if fail_step == step_type:
                yield {
                    "event": "step_failed",
                    **event,
                    "error_code": "mock_step_failed",
                    "error_class": "MockExecutionError",
                    "result_payload": {"mock": True},
                }
                yield {"event": "runtime_failed", "error_class": "MockExecutionError"}
                return

            if step_type == "set_username" and username_verify == "mismatch":
                yield {
                    "event": "step_uncertain",
                    **event,
                    "verification_attempted": True,
                    "verification_result": {
                        "editable_username": "other-user",
                        "active_usernames": ["other-user"],
                    },
                    "uncertain_reason": "username_verify_mismatch",
                    "result_payload": {"desired_username": payload.get("username")},
                }
                yield {"event": "runtime_closed"}
                return

            if step_type == "set_pinned_channel":
                channel_ref = (payload.get("pinned_channel_ref") or "").strip()
                mock_fail_channel = payload_json.get("mock_fail_pinned_channel")
                if mock_fail_channel and channel_ref == mock_fail_channel:
                    yield {
                        "event": "step_failed",
                        **event,
                        "error_code": "pinned_channel_not_found",
                        "error_class": "PinnedChannelResolutionError",
                        "result_payload": {"message": f"channel {channel_ref} not found"},
                    }
                    yield {"event": "runtime_failed", "error_class": "PinnedChannelResolutionError"}
                    return
                if channel_ref.startswith("@"):
                    resolved_id = hash(channel_ref) % 10**12
                    payload = {**payload, "_resolved_chat_id": resolved_id}
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": False,
                    "verification_result": None,
                    "result_payload": {"applied": payload},
                }
                continue

            if step_type in {"post_story_image", "post_story_video"}:
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": True,
                    "verification_result": {"status": "posted"},
                    "result_payload": _post_story_result(payload, step_type),
                }
                continue

            builder = _DEFAULT_VERIFICATION_RESULTS.get(step_type, _result_mock_applied)
            yield {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": builder(payload, ctx),
            }

        yield {"event": "runtime_closed"}
