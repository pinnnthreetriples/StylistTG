"""Tests for MockProfileExecutionAdapter and ProfileExecutionAdapter protocol.

Covers the mock adapter's event generation across different step types,
failure simulation, and crash simulation.
"""

from __future__ import annotations

import pytest

from app.adapters.profile_execution import MockProfileExecutionAdapter


def _execute_step(step_type: str, payload: dict, context: dict | None = None):
    """Execute a single-step plan and return the event list."""
    adapter = MockProfileExecutionAdapter()
    plan = {"steps": [{"step_key": "s1", "step_type": step_type, "payload": payload}]}
    return list(adapter.execute("acc-1", plan, context or {}))


def test_mock_adapter_basic_set_name():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [{"step_key": "s1", "step_type": "set_name", "payload": {"name": "Alice Bob"}}]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    event_types = [e["event"] for e in events]
    assert "runtime_started" in event_types
    assert "step_started" in event_types
    assert "step_succeeded" in event_types


def test_mock_adapter_set_username():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [{"step_key": "s1", "step_type": "set_username", "payload": {"username": "test"}}]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1


def test_mock_adapter_set_username_verify_mismatch():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [{"step_key": "s1", "step_type": "set_username", "payload": {"username": "test"}}]
    }
    payload_json = {"mock_username_verify": "mismatch"}
    events = list(adapter.execute("acc-1", plan, payload_json))
    uncertain = [e for e in events if e["event"] == "step_uncertain"]
    assert len(uncertain) == 1
    assert uncertain[0]["uncertain_reason"] == "username_verify_mismatch"


def test_mock_adapter_set_bio():
    adapter = MockProfileExecutionAdapter()
    plan = {"steps": [{"step_key": "s1", "step_type": "set_bio", "payload": {"bio": "Hello!"}}]}
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1


def test_mock_adapter_set_profile_photo():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [
            {
                "step_key": "s1",
                "step_type": "set_profile_photo",
                "payload": {"asset_path": "/tmp/photo.jpg"},
            }
        ]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1


def test_mock_adapter_upload_profile_audio():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [
            {
                "step_key": "s1",
                "step_type": "upload_profile_audio",
                "payload": {"asset_path": "/tmp/audio.mp3", "audio_asset_id": "a1"},
            }
        ]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1
    assert "telegram_file_id" in succeeded[0].get("result_payload", {})


def test_mock_adapter_add_profile_audio():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [
            {
                "step_key": "s1",
                "step_type": "add_profile_audio",
                "payload": {"telegram_file_id": 42, "audio_asset_id": "a1"},
            }
        ]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1


def test_mock_adapter_remove_profile_audio():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [
            {
                "step_key": "s1",
                "step_type": "remove_profile_audio",
                "payload": {"telegram_file_id": 42},
            }
        ]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1
    assert succeeded[0].get("result_payload", {}).get("profile_audio_removed") is True


def test_mock_adapter_post_story_image():
    events = _execute_step(
        "post_story_image", {"asset_path": "/tmp/story.jpg", "asset_id": "story-1"}
    )
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 1
    rp = succeeded[0].get("result_payload", {})
    assert "story_post" in rp
    assert rp["story_post"]["media_kind"] == "image"


def test_mock_adapter_forced_failure():
    adapter = MockProfileExecutionAdapter()
    plan = {"steps": [{"step_key": "s1", "step_type": "set_bio", "payload": {"bio": "x"}}]}
    payload_json = {"mock_fail_step": "set_bio"}
    events = list(adapter.execute("acc-1", plan, payload_json))
    failed = [e for e in events if e["event"] == "step_failed"]
    assert len(failed) == 1
    assert failed[0]["error_code"] == "mock_step_failed"


def test_mock_adapter_crash_simulation():
    adapter = MockProfileExecutionAdapter()
    plan = {"steps": [{"step_key": "s1", "step_type": "set_name", "payload": {"name": "Test"}}]}
    payload_json = {"mock_crash_after_step_started": "set_name"}
    with pytest.raises(SystemExit):
        list(adapter.execute("acc-1", plan, payload_json))


def test_mock_adapter_multiple_steps():
    adapter = MockProfileExecutionAdapter()
    plan = {
        "steps": [
            {"step_key": "s1", "step_type": "set_name", "payload": {"name": "Alice"}},
            {"step_key": "s2", "step_type": "set_bio", "payload": {"bio": "Hello"}},
            {"step_key": "s3", "step_type": "set_username", "payload": {"username": "alice"}},
        ]
    }
    events = list(adapter.execute("acc-1", plan, {}))
    succeeded = [e for e in events if e["event"] == "step_succeeded"]
    assert len(succeeded) == 3


def test_mock_adapter_inspect_runtime():
    adapter = MockProfileExecutionAdapter()
    result = adapter.inspect_runtime("acc-1")
    assert result["ok"] is True
    assert result["runtime_health"] == "ready"
