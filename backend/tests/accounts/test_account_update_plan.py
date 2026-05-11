from app.services.account_update_plan import (
    build_account_update_plan,
    compute_account_update_intent_hash,
    normalize_account_update_desired_state,
    profile_payload_to_account_update_desired_state,
)


def test_profile_payload_maps_to_account_update_desired_state() -> None:
    desired = profile_payload_to_account_update_desired_state(
        {
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": "asset-1",
        }
    )

    assert desired == {
        "profile": {
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": "asset-1",
        },
        "profile_audio": {"action": "keep", "audio_asset_id": None},
        "stories": [],
    }


def test_account_update_plan_contains_current_profile_steps_with_policies() -> None:
    desired = profile_payload_to_account_update_desired_state(
        {
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": "asset-1",
            "photo_asset_path": "/tmp/profile.jpg",
        }
    )
    plan = build_account_update_plan(desired)

    assert plan["workflow_type"] == "account_update"
    assert plan["workflow_version"] == 1
    assert plan["job_payload_version"] == 2
    assert [step["step_type"] for step in plan["steps"]] == [
        "set_name",
        "set_bio",
        "set_username",
        "set_profile_photo",
    ]
    assert {step["capability_key"] for step in plan["steps"]} == {"profile_text", "profile_photo"}
    assert all(step["retry_policy"] == "standard" for step in plan["steps"])
    assert all("compensation_policy" in step for step in plan["steps"])


def test_account_update_plan_appends_profile_audio_add_steps() -> None:
    desired = normalize_account_update_desired_state(
        {
            "profile": {"name": "Stylist TG"},
            "profile_audio": {
                "action": "add",
                "audio_asset_id": "audio-1",
                "audio_asset_path": "/tmp/profile-audio.mp3",
                "title": "Track title",
            },
        }
    )
    plan = build_account_update_plan(desired)

    assert [step["step_type"] for step in plan["steps"]] == [
        "set_name",
        "set_bio",
        "set_username",
        "set_profile_photo",
        "upload_profile_audio",
        "add_profile_audio",
    ]
    audio_steps = plan["steps"][-2:]
    assert {step["capability_key"] for step in audio_steps} == {"profile_audio"}
    assert audio_steps[0]["payload"]["audio_asset_id"] == "audio-1"
    assert audio_steps[0]["payload"]["asset_path"] == "/tmp/profile-audio.mp3"
    assert audio_steps[0]["payload"]["title"] == "Track title"


def test_account_update_plan_appends_profile_audio_remove_step() -> None:
    desired = normalize_account_update_desired_state(
        {
            "profile": {"name": "Stylist TG"},
            "profile_audio": {"action": "remove"},
        }
    )
    plan = build_account_update_plan(desired)

    assert plan["steps"][-1]["step_type"] == "remove_profile_audio"
    assert plan["steps"][-1]["capability_key"] == "profile_audio"


def test_account_update_intent_hash_is_stable_for_key_order() -> None:
    desired_a = normalize_account_update_desired_state(
        {
            "profile": {
                "name": "Stylist TG",
                "bio": "Profile editor",
                "username": "stylist",
                "photo_asset_id": "asset-1",
            },
            "profile_audio": {"action": "keep"},
        }
    )
    desired_b = normalize_account_update_desired_state(
        {
            "profile_audio": {"action": "keep"},
            "profile": {
                "photo_asset_id": "asset-1",
                "username": "stylist",
                "bio": "Profile editor",
                "name": "Stylist TG",
            },
        }
    )

    assert compute_account_update_intent_hash("account-1", desired_a) == compute_account_update_intent_hash(
        "account-1", desired_b
    )


def test_stories_are_rejected_until_feature_is_enabled() -> None:
    desired = normalize_account_update_desired_state(
        {
            "profile": {"name": "Stylist TG"},
            "stories": [{"action": "post_image", "asset_id": "asset-story", "caption": "Launch"}],
        }
    )
    plan = build_account_update_plan(desired)

    assert [step["step_type"] for step in plan["steps"]][-3:] == [
        "validate_story_capabilities",
        "prepare_story_media",
        "post_story_image",
    ]


def test_account_update_rejects_unsupported_selected_users_story_privacy() -> None:
    try:
        normalize_account_update_desired_state(
            {
                "profile": {"name": "Stylist TG"},
                "stories": [
                    {
                        "action": "post_image",
                        "asset_id": "asset-story",
                        "privacy_preset": "selected_users",
                    }
                ],
            }
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "unsupported story privacy_preset"
