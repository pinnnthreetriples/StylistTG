from __future__ import annotations

import pytest

from app.main import app
from app.models import (
    AccountProfileState,
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
)
from app.services.account_profile_completeness import (
    ProfileCompletenessAccountNotFound,
    evaluate,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from tests.helpers.factories import seed_account, seed_two_workspaces


def _auth(workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID) -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=workspace_id,
        role="viewer",
        auth_source="test",
    )


@pytest.fixture()
def viewer_client(app_client):
    app.dependency_overrides[get_current_auth_context] = lambda: _auth()
    return app_client


def _set_profile(
    db_session,
    account_id: str,
    *,
    first_name: str | None = None,
    bio: str | None = None,
    username: str | None = None,
    profile_photo_asset_id: str | None = None,
) -> None:
    db_session.add(
        AccountProfileState(
            account_id=account_id,
            first_name=first_name,
            bio=bio,
            username=username,
            profile_photo_asset_id=profile_photo_asset_id,
        )
    )
    db_session.commit()


def test_empty_account_scores_zero_and_lists_required_missing(db_session) -> None:
    account = seed_account(db_session)

    report = evaluate(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
    )

    expected = {
        "score": 0.0,
        "missing_required": ["first_name", "bio", "profile_photo_asset_id"],
        "missing_recommended": ["username", "pinned_channel_ref"],
    }
    assert {key: getattr(report, key) for key in expected} == expected


def test_all_fields_filled_scores_one(db_session) -> None:
    account = seed_account(db_session)
    account.pinned_channel_ref = "@channel"
    _set_profile(
        db_session,
        account.id,
        first_name="Anna",
        bio="Long enough bio",
        username="anna",
        profile_photo_asset_id="00000000-0000-4000-8000-000000000101",
    )

    report = evaluate(db_session, workspace_id=account.workspace_id, account_id=account.id)

    assert report.score == 1.0
    assert report.missing_required == []
    assert report.missing_recommended == []


def test_required_fields_only_scores_point_eight(db_session) -> None:
    account = seed_account(db_session)
    _set_profile(
        db_session,
        account.id,
        first_name="Bo",
        bio="Complete bio text",
        profile_photo_asset_id="00000000-0000-4000-8000-000000000102",
    )

    report = evaluate(db_session, workspace_id=account.workspace_id, account_id=account.id)

    assert report.score == 0.8
    assert report.missing_recommended == ["username", "pinned_channel_ref"]


def test_one_character_first_name_is_missing(db_session) -> None:
    account = seed_account(db_session)
    _set_profile(db_session, account.id, first_name="A")

    report = evaluate(db_session, workspace_id=account.workspace_id, account_id=account.id)

    assert report.breakdown["first_name"] is False
    assert "first_name" in report.missing_required


def test_short_bio_is_missing(db_session) -> None:
    account = seed_account(db_session)
    _set_profile(db_session, account.id, bio="Hi")

    report = evaluate(db_session, workspace_id=account.workspace_id, account_id=account.id)

    assert report.breakdown["bio"] is False
    assert "bio" in report.missing_required


def test_cross_tenant_service_lookup_raises_not_found(db_session) -> None:
    _workspace_a, workspace_b = seed_two_workspaces(db_session)
    account = seed_account(db_session, external_ref="+15550109990", workspace_id=workspace_b)

    with pytest.raises(ProfileCompletenessAccountNotFound):
        evaluate(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, account_id=account.id)


def test_api_returns_report_and_cross_tenant_404(viewer_client, db_session) -> None:
    workspace_a, workspace_b = seed_two_workspaces(db_session)
    account_a = seed_account(db_session, external_ref="+15550109991", workspace_id=workspace_a)
    account_b = seed_account(db_session, external_ref="+15550109992", workspace_id=workspace_b)
    _set_profile(db_session, account_a.id, first_name="Cara", bio="Ready profile")

    ok_response = viewer_client.get(f"/api/accounts/{account_a.id}/profile-completeness")
    not_found_response = viewer_client.get(f"/api/accounts/{account_b.id}/profile-completeness")

    assert ok_response.status_code == 200
    assert ok_response.json()["account_id"] == account_a.id
    assert not_found_response.status_code == 404
    body = not_found_response.json()
    assert "detail" in body or "error_code" in body
