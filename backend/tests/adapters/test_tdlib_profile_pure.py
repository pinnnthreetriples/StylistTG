"""Unit tests for pure / mockable functions in app.adapters.tdlib_profile_execution.

These tests cover pure helper functions, error classes, and the
UnavailableProfileExecutionAdapter — code that does NOT require a real
TDLib shared library.
"""

from __future__ import annotations

import pytest

from app.adapters.tdlib_profile_execution import (
    TdlibProfileQueryError,
    TdlibStoryPostUncertain,
    UnavailableProfileExecutionAdapter,
    _can_post_story_error_code,
    _dict_or_empty,
    _extract_message_audio_file,
    _profile_tdlib_error_code,
    _story_content,
    _story_privacy_settings,
    _tdlib_file_debug_payload,
    _tdlib_file_upload_completed,
    _tdlib_file_upload_ready_for_profile_audio,
    classify_job_outcome,
    classify_step_outcome,
    map_step_to_tdlib_query,
    split_name,
    verify_username_result,
)
from app.models import JobState, StepStatus


# ---------------------------------------------------------------------------
# split_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "full_name,expected",
    [
        (None, ("", "")),
        ("", ("", "")),
        ("  ", ("", "")),
        ("Alice", ("Alice", "")),
        ("Alice Bob", ("Alice", "Bob")),
        ("Alice Bob Charlie", ("Alice", "Bob Charlie")),
        ("  Alice  ", ("Alice", "")),
    ],
)
def test_split_name(full_name, expected):
    assert split_name(full_name) == expected


# ---------------------------------------------------------------------------
# map_step_to_tdlib_query
# ---------------------------------------------------------------------------


def test_map_step_set_name_explicit():
    q = map_step_to_tdlib_query(
        {"step_type": "set_name", "payload": {"first_name": "A", "last_name": "B"}}
    )
    assert q == {"@type": "setName", "first_name": "A", "last_name": "B"}


def test_map_step_set_name_from_full_name():
    q = map_step_to_tdlib_query({"step_type": "set_name", "payload": {"name": "Alice Bob"}})
    assert q == {"@type": "setName", "first_name": "Alice", "last_name": "Bob"}


def test_map_step_set_bio():
    q = map_step_to_tdlib_query({"step_type": "set_bio", "payload": {"bio": "hello"}})
    assert q == {"@type": "setBio", "bio": "hello"}


def test_map_step_set_username():
    q = map_step_to_tdlib_query({"step_type": "set_username", "payload": {"username": "user1"}})
    assert q == {"@type": "setUsername", "username": "user1"}


def test_map_step_set_profile_photo():
    q = map_step_to_tdlib_query(
        {"step_type": "set_profile_photo", "payload": {"asset_path": "/tmp/photo.jpg"}}
    )
    assert q["@type"] == "setProfilePhoto"
    assert q["photo"]["photo"]["path"] == "/tmp/photo.jpg"


def test_map_step_add_profile_audio():
    q = map_step_to_tdlib_query(
        {"step_type": "add_profile_audio", "payload": {"telegram_file_id": 42}}
    )
    assert q == {"@type": "addProfileAudio", "file_id": 42}


def test_map_step_add_profile_audio_missing_file_id():
    with pytest.raises(ValueError, match="telegram_file_id"):
        map_step_to_tdlib_query({"step_type": "add_profile_audio", "payload": {}})


def test_map_step_remove_profile_audio_with_id():
    q = map_step_to_tdlib_query(
        {"step_type": "remove_profile_audio", "payload": {"telegram_file_id": 99}}
    )
    assert q == {"@type": "removeProfileAudio", "file_id": 99}


def test_map_step_remove_profile_audio_fallback():
    q = map_step_to_tdlib_query({"step_type": "remove_profile_audio", "payload": {}})
    assert q == {"@type": "getMe"}


def test_map_step_validate_story_capabilities():
    q = map_step_to_tdlib_query(
        {"step_type": "validate_story_capabilities", "payload": {"any": True}}
    )
    assert q == {"@type": "getMe"}


def test_map_step_prepare_story_media():
    q = map_step_to_tdlib_query({"step_type": "prepare_story_media", "payload": {}})
    assert q == {"@type": "getMe"}


def test_map_step_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        map_step_to_tdlib_query({"step_type": "unknown_step", "payload": {}})


# ---------------------------------------------------------------------------
# verify_username_result
# ---------------------------------------------------------------------------


def test_verify_username_matched_editable():
    me = {"usernames": {"editable_username": "alice", "active_usernames": ["alice"]}}
    result = verify_username_result("alice", me)
    assert result["status"] == StepStatus.SUCCEEDED
    assert result["verification_attempted"] is True


def test_verify_username_matched_active():
    me = {"usernames": {"editable_username": "bob", "active_usernames": ["alice", "bob"]}}
    result = verify_username_result("alice", me)
    assert result["status"] == StepStatus.SUCCEEDED


def test_verify_username_mismatch():
    me = {"usernames": {"editable_username": "bob", "active_usernames": ["bob"]}}
    result = verify_username_result("alice", me)
    assert result["status"] == StepStatus.UNCERTAIN
    assert result["uncertain_reason"] == "username_verify_mismatch"


def test_verify_username_empty_response():
    result = verify_username_result("alice", {})
    assert result["status"] == StepStatus.UNCERTAIN


# ---------------------------------------------------------------------------
# classify_step_outcome / classify_job_outcome
# ---------------------------------------------------------------------------


def test_classify_step_outcome_uncertain():
    assert classify_step_outcome("set_name", "uncertain") == StepStatus.UNCERTAIN


def test_classify_step_outcome_failed():
    assert classify_step_outcome("set_name", "failed") == StepStatus.FAILED


def test_classify_step_outcome_succeeded():
    assert classify_step_outcome("set_name", "ok") == StepStatus.SUCCEEDED


def test_classify_job_outcome_completed():
    results = [{"status": StepStatus.SUCCEEDED, "step_type": "set_name"}]
    assert classify_job_outcome(results) == JobState.COMPLETED


def test_classify_job_outcome_failed():
    results = [
        {"status": StepStatus.SUCCEEDED, "step_type": "set_name"},
        {"status": StepStatus.FAILED, "step_type": "set_bio"},
    ]
    assert classify_job_outcome(results) == JobState.FAILED


def test_classify_job_outcome_manual_intervention_username():
    results = [{"status": StepStatus.UNCERTAIN, "step_type": "set_username"}]
    assert classify_job_outcome(results) == JobState.MANUAL_INTERVENTION_NEEDED


def test_classify_job_outcome_partially_completed():
    results = [{"status": StepStatus.UNCERTAIN, "step_type": "set_bio"}]
    assert classify_job_outcome(results) == JobState.PARTIALLY_COMPLETED


# ---------------------------------------------------------------------------
# _story_content
# ---------------------------------------------------------------------------


def test_story_content_image():
    content = _story_content("image", "/tmp/story.jpg")
    assert content["@type"] == "inputStoryContentPhoto"
    assert content["photo"]["path"] == "/tmp/story.jpg"


def test_story_content_video():
    content = _story_content("video", "/tmp/story.mp4")
    assert content["@type"] == "inputStoryContentVideo"
    assert content["video"]["path"] == "/tmp/story.mp4"
    assert content["is_animation"] is False


# ---------------------------------------------------------------------------
# _story_privacy_settings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("preset", [None, "", "contacts"])
def test_story_privacy_contacts(preset):
    result = _story_privacy_settings(preset)
    assert result["@type"] == "storyPrivacySettingsContacts"


def test_story_privacy_public():
    result = _story_privacy_settings("public")
    assert result["@type"] == "storyPrivacySettingsEveryone"


def test_story_privacy_close_friends():
    result = _story_privacy_settings("close_friends")
    assert result["@type"] == "storyPrivacySettingsCloseFriends"


def test_story_privacy_unsupported():
    with pytest.raises(TdlibProfileQueryError, match="Unsupported"):
        _story_privacy_settings("custom_invalid")


# ---------------------------------------------------------------------------
# _can_post_story_error_code
# ---------------------------------------------------------------------------


def test_can_post_story_error_code_none():
    assert _can_post_story_error_code(None) == "CAN_POST_STORY_UNKNOWN"


def test_can_post_story_error_code_empty():
    assert _can_post_story_error_code("") == "CAN_POST_STORY_UNKNOWN"


def test_can_post_story_error_code_premium_needed():
    code = _can_post_story_error_code("canPostStoryResultPremiumNeeded")
    assert code.startswith("CAN_POST_STORY_")
    assert "PREMIUM" in code


# ---------------------------------------------------------------------------
# _dict_or_empty
# ---------------------------------------------------------------------------


def test_dict_or_empty_with_dict():
    assert _dict_or_empty({"a": 1}) == {"a": 1}


def test_dict_or_empty_with_none():
    assert _dict_or_empty(None) == {}


def test_dict_or_empty_with_list():
    assert _dict_or_empty([1, 2]) == {}


# ---------------------------------------------------------------------------
# _tdlib_file_upload_completed / _tdlib_file_upload_ready_for_profile_audio
# ---------------------------------------------------------------------------


def test_file_upload_completed_true():
    assert _tdlib_file_upload_completed({"remote": {"is_uploading_completed": True}}) is True


def test_file_upload_completed_false():
    assert _tdlib_file_upload_completed({"remote": {"is_uploading_completed": False}}) is False


def test_file_upload_completed_no_remote():
    assert _tdlib_file_upload_completed({}) is False


def test_file_upload_ready_completed():
    assert (
        _tdlib_file_upload_ready_for_profile_audio({"remote": {"is_uploading_completed": True}})
        is True
    )


def test_file_upload_ready_size_based():
    response = {
        "remote": {
            "is_uploading_completed": False,
            "is_uploading_active": False,
            "uploaded_size": 1000,
        },
        "expected_size": 1000,
    }
    assert _tdlib_file_upload_ready_for_profile_audio(response) is True


def test_file_upload_not_ready_uploading_active():
    response = {
        "remote": {
            "is_uploading_completed": False,
            "is_uploading_active": True,
            "uploaded_size": 500,
        },
        "expected_size": 1000,
    }
    assert _tdlib_file_upload_ready_for_profile_audio(response) is False


def test_file_upload_not_ready_size_mismatch():
    response = {
        "remote": {
            "is_uploading_completed": False,
            "is_uploading_active": False,
            "uploaded_size": 500,
        },
        "expected_size": 1000,
    }
    assert _tdlib_file_upload_ready_for_profile_audio(response) is False


def test_file_upload_not_ready_no_remote():
    assert _tdlib_file_upload_ready_for_profile_audio({}) is False


# ---------------------------------------------------------------------------
# _tdlib_file_debug_payload
# ---------------------------------------------------------------------------


def test_file_debug_payload_full():
    file_obj = {
        "id": 42,
        "size": 1000,
        "expected_size": 1000,
        "remote": {
            "is_uploading_active": False,
            "is_uploading_completed": True,
            "uploaded_size": 1000,
            "id": "remote-id",
            "unique_id": "u-id",
        },
        "local": {"is_downloading_completed": True, "downloaded_prefix_size": 0},
    }
    payload = _tdlib_file_debug_payload(file_obj)
    assert payload["id"] == 42
    assert payload["remote"]["has_id"] is True
    assert payload["local"]["is_downloading_completed"] is True


def test_file_debug_payload_none():
    assert _tdlib_file_debug_payload(None) == {}


def test_file_debug_payload_no_remote_local():
    payload = _tdlib_file_debug_payload({"id": 1, "size": 100, "expected_size": 100})
    assert "remote" not in payload
    assert "local" not in payload


# ---------------------------------------------------------------------------
# _extract_message_audio_file
# ---------------------------------------------------------------------------


def test_extract_message_audio_file_valid():
    message = {
        "content": {
            "@type": "messageAudio",
            "audio": {"audio": {"id": 55, "remote": {}}},
        }
    }
    result = _extract_message_audio_file(message)
    assert result["id"] == 55


def test_extract_message_audio_file_wrong_type():
    message = {"content": {"@type": "messageText"}}
    assert _extract_message_audio_file(message) == {}


def test_extract_message_audio_file_no_content():
    assert _extract_message_audio_file({}) == {}


def test_extract_message_audio_file_no_audio_inner():
    message = {"content": {"@type": "messageAudio", "audio": {}}}
    assert _extract_message_audio_file(message) == {}


# ---------------------------------------------------------------------------
# _profile_tdlib_error_code
# ---------------------------------------------------------------------------


def test_profile_tdlib_error_code_username_prefix():
    code = _profile_tdlib_error_code({"message": "USERNAME_INVALID"}, None)
    assert code == "USERNAME_INVALID"


def test_profile_tdlib_error_code_flood_prefix():
    code = _profile_tdlib_error_code({"message": "FLOOD_WAIT_60"}, None)
    assert code == "FLOOD_WAIT_60"


def test_profile_tdlib_error_code_fallback_to_marker():
    code = _profile_tdlib_error_code({"message": "Some error"}, "tdlib_hard_stop:frozen")
    assert code == "frozen"


def test_profile_tdlib_error_code_fallback_no_marker():
    code = _profile_tdlib_error_code({"message": "Some error"}, None)
    assert code == "tdlib_profile_step_failed"


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


def test_tdlib_profile_query_error():
    err = TdlibProfileQueryError("oops", error_code="E1")
    assert str(err) == "oops"
    assert err.error_code == "E1"


def test_tdlib_story_post_uncertain():
    err = TdlibStoryPostUncertain(
        "timeout",
        uncertain_reason="story_post_confirmation_timeout",
        verification_result={"status": "posting"},
        result_payload={"story_post": {}},
    )
    assert err.uncertain_reason == "story_post_confirmation_timeout"
    assert err.result_payload == {"story_post": {}}


# ---------------------------------------------------------------------------
# UnavailableProfileExecutionAdapter
# ---------------------------------------------------------------------------


def test_unavailable_adapter_inspect_runtime():
    adapter = UnavailableProfileExecutionAdapter("lib not found")
    result = adapter.inspect_runtime("account-1")
    assert result["ok"] is False
    assert result["error"] == "lib not found"


def test_unavailable_adapter_execute():
    adapter = UnavailableProfileExecutionAdapter("lib not found")
    events = list(adapter.execute("account-1", {"steps": []}, {}))
    assert len(events) == 1
    assert events[0]["event"] == "runtime_failed"
    assert events[0]["error_code"] == "TDLIB_UNAVAILABLE"
