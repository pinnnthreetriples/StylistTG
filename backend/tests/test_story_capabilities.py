from fastapi.testclient import TestClient

from app.config import Settings
from app.db import get_session
from app.main import app
from app.services.story_capabilities import build_story_capabilities
from app.services.accounts import create_account


def override_session(session):
    def _override():
        yield session

    return _override


def test_story_capabilities_returns_safe_policy(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()
    app.dependency_overrides[get_session] = override_session(db_session)
    client = TestClient(app)

    response = client.get(f"/api/story-capabilities/{account.id}")

    app.dependency_overrides.clear()
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


def test_story_capabilities_enable_photo_and_video_for_tdlib_live_phase(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.commit()

    payload = build_story_capabilities(
        db_session,
        account.id,
        config=Settings(profile_execution_adapter="tdlib", stories_tdlib_live_enabled=True),
    )

    assert payload["tdlib_live_publishing_enabled"] is True
    assert payload["can_prepare_image"] is True
    assert payload["can_prepare_video"] is True
    assert "story video TDLib execution is not enabled" not in payload["warnings"]
