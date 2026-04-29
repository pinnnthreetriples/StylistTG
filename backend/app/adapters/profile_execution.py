from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from app.models import AccountState


class ProfileExecutionAdapter(Protocol):
    def execute(self, account_id: str, plan_json_snapshot: dict, payload_json: dict) -> Iterator[dict]:
        """Yield structured execution events for a profile job."""


class MockProfileExecutionAdapter:
    def inspect_runtime(self, account_id: str) -> dict:
        return {
            "ok": True,
            "account_state": AccountState.EXECUTION_USABLE,
            "runtime_health": "ready",
            "telegram_user_id": "mock-user",
            "error": None,
        }

    def execute(self, account_id: str, plan_json_snapshot: dict, payload_json: dict) -> Iterator[dict]:
        yield {"event": "runtime_started"}
        fail_step = payload_json.get("mock_fail_step")
        crash_step = payload_json.get("mock_crash_after_step_started")
        username_verify = payload_json.get("mock_username_verify")
        uploaded_audio_file_id: str | None = None

        for step in plan_json_snapshot["steps"]:
            event = {
                "step_key": step["step_key"],
                "step_type": step["step_type"],
            }
            yield {"event": "step_started", **event}

            if crash_step == step["step_type"]:
                raise SystemExit(2)

            if fail_step == step["step_type"]:
                yield {
                    "event": "step_failed",
                    **event,
                    "error_code": "mock_step_failed",
                    "error_class": "MockExecutionError",
                    "result_payload": {"mock": True},
                }
                yield {"event": "runtime_failed", "error_class": "MockExecutionError"}
                return

            if step["step_type"] == "set_username" and username_verify == "mismatch":
                yield {
                    "event": "step_uncertain",
                    **event,
                    "verification_attempted": True,
                    "verification_result": {
                        "editable_username": "other-user",
                        "active_usernames": ["other-user"],
                    },
                    "uncertain_reason": "username_verify_mismatch",
                    "result_payload": {"desired_username": step["payload"].get("username")},
                }
                yield {"event": "runtime_closed"}
                return

            if step["step_type"] == "upload_profile_audio":
                audio_asset_id = step["payload"].get("audio_asset_id")
                uploaded_audio_file_id = f"mock-file-{audio_asset_id}"
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": False,
                    "verification_result": None,
                    "result_payload": {
                        "audio_asset_id": audio_asset_id,
                        "telegram_file_id": uploaded_audio_file_id,
                    },
                }
                continue

            if step["step_type"] == "add_profile_audio":
                audio_asset_id = step["payload"].get("audio_asset_id")
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": False,
                    "verification_result": None,
                    "result_payload": {
                        "profile_audio": {
                            "source_asset_id": audio_asset_id,
                            "telegram_file_id": uploaded_audio_file_id or f"mock-file-{audio_asset_id}",
                            "title": None,
                            "performer": None,
                            "duration_seconds": None,
                            "mime": None,
                        }
                    },
                }
                continue

            if step["step_type"] == "remove_profile_audio":
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": False,
                    "verification_result": None,
                    "result_payload": {"profile_audio_removed": True},
                }
                continue

            if step["step_type"] in {"validate_story_capabilities", "prepare_story_media"}:
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": False,
                    "verification_result": None,
                    "result_payload": {"mock": True, "applied": step["payload"]},
                }
                continue

            if step["step_type"] in {"post_story_image", "post_story_video"}:
                media_kind = "image" if step["step_type"] == "post_story_image" else "video"
                story_id = f"mock-story-{step['payload'].get('client_id')}"
                yield {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": True,
                    "verification_result": {"status": "posted"},
                    "result_payload": {
                        "story_post": {
                            "status": "posted",
                            "telegram_story_id": story_id,
                            "temporary_story_id": story_id,
                            "media_kind": media_kind,
                            "asset_id": step["payload"].get("asset_id"),
                            "caption": step["payload"].get("caption"),
                            "privacy_preset": step["payload"].get("privacy_preset"),
                            "active_period_seconds": step["payload"].get("active_period_seconds"),
                            "protect_content": step["payload"].get("protect_content"),
                        }
                    },
                }
                continue

            yield {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {"mock": True, "applied": step["payload"]},
            }

        yield {"event": "runtime_closed"}
