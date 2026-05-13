from __future__ import annotations

import pytest

from app.config import Settings
from app.models import AccountState, AssetKind, JobState, utc_now
from app.modules.account_editing.policies import AccountEditingPolicy
from app.modules.account_editing.planner import normalize_account_update_desired_state
from app.services.accounts import create_account
from conftest import seed_audio_asset, seed_story_asset
from tests.helpers.factories import seed_account_with_profile, seed_profile_job


def test_preview_blockers_preserve_manual_intervention_and_state_messages(db_session) -> None:
    account = create_account(db_session, external_ref="+15550104101")
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    db_session.commit()
    desired_state = normalize_account_update_desired_state({"profile": {"name": "Stylist TG"}})

    blocking_errors, warnings, _ = AccountEditingPolicy(db_session).preview_safety(
        account=account,
        account_id=account.id,
        desired_state=desired_state,
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert isinstance(warnings, list)
    assert "account requires manual intervention" in blocking_errors
    assert "account is not execution_usable" in blocking_errors


def test_preview_cooldown_message_is_unchanged(db_session) -> None:
    account = seed_account_with_profile(db_session, external_ref="+15550104102")
    seed_profile_job(
        db_session,
        account_id=account.id,
        state=JobState.COMPLETED,
        finished_at=utc_now(),
    )
    desired_state = normalize_account_update_desired_state({"profile": {"username": "stylist"}})

    blocking_errors, _, _ = AccountEditingPolicy(db_session).preview_safety(
        account=account,
        account_id=account.id,
        desired_state=desired_state,
        config=Settings(profile_job_cooldown_seconds=3600),
    )

    assert "profile job cooldown active" in blocking_errors


def test_create_policy_preserves_story_gate_errors(db_session) -> None:
    account = seed_account_with_profile(db_session, external_ref="+15550104103")
    desired_state = normalize_account_update_desired_state(
        {"stories": [{"action": "post_image", "asset_id": "story-1"}]}
    )
    policy = AccountEditingPolicy(db_session)

    with pytest.raises(ValueError, match="^stories are disabled$"):
        policy.validate_job_creation(
            account=account,
            account_id=account.id,
            desired_state=desired_state,
            config=Settings(stories_enabled=False),
        )

    with pytest.raises(ValueError, match="^stories live TDLib execution is not enabled$"):
        policy.validate_job_creation(
            account=account,
            account_id=account.id,
            desired_state=desired_state,
            config=Settings(
                stories_enabled=True,
                profile_execution_adapter="tdlib",
                stories_tdlib_live_enabled=False,
            ),
        )


def test_profile_audio_validation_preserves_error_messages(db_session) -> None:
    account = seed_account_with_profile(db_session, external_ref="+15550104104")
    audio = seed_audio_asset(db_session)
    audio.mime = "audio/ogg"
    db_session.commit()

    with pytest.raises(ValueError, match="^profile audio must be MP3 or M4A$"):
        AccountEditingPolicy(db_session).normalize_desired_state_with_assets(
            account_id=account.id,
            desired_state={
                "profile_audio": {"action": "add", "audio_asset_id": audio.id},
            },
            workspace_id=account.workspace_id,
        )


def test_story_asset_validation_preserves_error_messages(db_session) -> None:
    account = seed_account_with_profile(db_session, external_ref="+15550104105")
    story = seed_story_asset(db_session, kind=AssetKind.STORY_VIDEO)

    with pytest.raises(ValueError, match="^asset kind is not story_image$"):
        AccountEditingPolicy(db_session).normalize_desired_state_with_assets(
            account_id=account.id,
            desired_state={
                "stories": [{"action": "post_image", "asset_id": story.id}],
            },
            workspace_id=account.workspace_id,
        )
