
from app.config import Settings
from app.services.story_capabilities import build_story_capabilities
from app.services.accounts import create_account


def test_story_capabilities_returns_safe_policy(app_client, db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()
    response = app_client.get(f"/api/story-capabilities/{account.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == account.id
    assert payload["allowed_active_period_seconds"] == [86400]
    assert payload["tdlib_live_publishing_enabled"] is False
    assert "stories live TDLib publishing requires TDLib profile execution" in payload["warnings"]


def test_story_capabilities_live_false_for_mock_even_when_story_flag_enabled(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()

    payload = build_story_capabilities(
        db_session,
        account.id,
        config=Settings(
            profile_execution_adapter="mock",
            stories_enabled=True,
            stories_tdlib_live_enabled=True,
        ),
    )

    assert payload["tdlib_live_publishing_enabled"] is False
    assert "stories live TDLib publishing requires TDLib profile execution" in payload["warnings"]


def test_story_capabilities_reports_disabled_stories(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()

    payload = build_story_capabilities(
        db_session,
        account.id,
        config=Settings(
            profile_execution_adapter="tdlib",
            stories_enabled=False,
            stories_tdlib_live_enabled=True,
        ),
    )

    assert payload["tdlib_live_publishing_enabled"] is False
    assert "stories are disabled" in payload["warnings"]


def test_story_capabilities_enable_photo_and_video_for_tdlib_live_phase(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()
    monkeypatch.setattr("app.services.story_capabilities._binary_available", lambda configured_path, fallback_name: True)

    payload = build_story_capabilities(
        db_session,
        account.id,
        config=Settings(profile_execution_adapter="tdlib", stories_tdlib_live_enabled=True),
    )

    assert payload["tdlib_live_publishing_enabled"] is True
    assert payload["can_prepare_image"] is True
    assert payload["can_prepare_video"] is True
    assert "story video TDLib execution is not enabled" not in payload["warnings"]


def test_story_capabilities_block_video_preparation_when_media_tools_missing(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()

    payload = build_story_capabilities(
        db_session,
        account.id,
        config=Settings(
            profile_execution_adapter="tdlib",
            stories_tdlib_live_enabled=True,
            ffprobe_path="missing-ffprobe-for-test",
            ffmpeg_path="missing-ffmpeg-for-test",
        ),
    )

    assert payload["can_prepare_video"] is False
    assert "story video preparation is limited until ffprobe and ffmpeg are available" in payload["warnings"]
