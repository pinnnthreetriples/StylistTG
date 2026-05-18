from __future__ import annotations

import pytest

from app.config import Settings
from app.models import AccountState, AssetKind
from app.modules.account_editing.errors import (
    AccountAssetKindInvalidError,
    AccountAssetNotFoundError,
    ProfileAudioUnsupportedFormatError,
    StoriesDisabledError,
    StoriesTdlibLiveDisabledError,
)
from app.modules.account_editing.policies import AccountEditingPolicy
from app.modules.account_editing.planner import normalize_account_update_desired_state
from app.services.accounts import create_account
from conftest import seed_audio_asset
from tests.helpers.factories import seed_account_with_profile


def _policy(db_session) -> AccountEditingPolicy:
    return AccountEditingPolicy(db_session)


def _normalized_profile(**profile):
    return normalize_account_update_desired_state({"profile": profile})


def test_requested_profile_fields_returns_only_requested_profile_keys(db_session) -> None:
    desired_state = {"profile": {"name": "Stylist TG", "username": None}, "stories": []}

    assert _policy(db_session).requested_profile_fields(desired_state) == {"name", "username"}


def test_requested_profile_fields_ignores_missing_or_non_mapping_profile(db_session) -> None:
    policy = _policy(db_session)

    assert policy.requested_profile_fields({}) == set()
    assert policy.requested_profile_fields({"profile": None}) == set()
    assert policy.requested_profile_fields({"profile": ["name"]}) == set()


def test_changed_profile_step_types_detects_name_change(db_session) -> None:
    account = seed_account_with_profile(db_session)
    account.profile_state.first_name = "Old"
    account.profile_state.last_name = ""
    db_session.commit()
    desired_state = _normalized_profile(name="New")

    steps = _policy(db_session).changed_profile_step_types(
        account=account,
        desired_state=desired_state,
        requested_profile_fields={"name"},
    )

    assert steps == {"set_name"}


def test_changed_profile_step_types_detects_bio_change(db_session) -> None:
    account = seed_account_with_profile(db_session)
    desired_state = _normalized_profile(bio="Updated bio")

    steps = _policy(db_session).changed_profile_step_types(
        account=account,
        desired_state=desired_state,
        requested_profile_fields={"bio"},
    )

    assert steps == {"set_bio"}


def test_changed_profile_step_types_detects_username_change(db_session) -> None:
    account = seed_account_with_profile(db_session, index=9)
    desired_state = _normalized_profile(username="newusername")

    steps = _policy(db_session).changed_profile_step_types(
        account=account,
        desired_state=desired_state,
        requested_profile_fields={"username"},
    )

    assert steps == {"set_username"}


def test_changed_profile_step_types_skips_photo_when_asset_matches(db_session, monkeypatch) -> None:
    account = seed_account_with_profile(db_session)
    desired_state = _normalized_profile(photo_asset_id="asset-new")
    policy = _policy(db_session)

    monkeypatch.setattr(
        policy._repo, "latest_applied_profile_photo_asset_id", lambda _: "asset-new"
    )
    assert (
        policy.changed_profile_step_types(
            account=account,
            desired_state=desired_state,
            requested_profile_fields={"photo_asset_id"},
        )
        == set()
    )


def test_changed_profile_step_types_detects_photo_when_asset_differs(
    db_session, monkeypatch
) -> None:
    account = seed_account_with_profile(db_session)
    desired_state = _normalized_profile(photo_asset_id="asset-new")
    policy = _policy(db_session)

    monkeypatch.setattr(
        policy._repo, "latest_applied_profile_photo_asset_id", lambda _: "asset-old"
    )
    assert policy.changed_profile_step_types(
        account=account,
        desired_state=desired_state,
        requested_profile_fields={"photo_asset_id"},
    ) == {"set_profile_photo"}


def test_changed_profile_step_types_does_not_update_empty_matching_fields(db_session) -> None:
    account = seed_account_with_profile(db_session)
    account.profile_state.first_name = ""
    account.profile_state.last_name = ""
    account.profile_state.bio = None
    account.profile_state.username = None
    db_session.commit()
    desired_state = _normalized_profile(name="", bio="", username="")

    steps = _policy(db_session).changed_profile_step_types(
        account=account,
        desired_state=desired_state,
        requested_profile_fields={"name", "bio", "username"},
    )

    assert steps == set()


def test_preview_safety_returns_hard_stop_and_execution_usable_blockers(db_session) -> None:
    account = create_account(db_session, external_ref="+15550105001")
    account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    db_session.commit()

    blocking_errors, _, _ = _policy(db_session).preview_safety(
        account=account,
        account_id=account.id,
        desired_state=_normalized_profile(name="Stylist TG"),
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert "account requires manual intervention" in blocking_errors
    assert "account is not execution_usable" in blocking_errors


def test_validate_job_creation_blocks_stories_when_stories_disabled(db_session) -> None:
    account = seed_account_with_profile(db_session)
    desired_state = normalize_account_update_desired_state(
        {"stories": [{"action": "post_image", "asset_id": "story-missing"}]}
    )

    with pytest.raises(StoriesDisabledError, match="^stories are disabled$"):
        _policy(db_session).validate_job_creation(
            account=account,
            account_id=account.id,
            desired_state=desired_state,
            config=Settings(stories_enabled=False),
        )


def test_validate_job_creation_blocks_stories_when_tdlib_live_disabled(db_session) -> None:
    account = seed_account_with_profile(db_session)
    desired_state = normalize_account_update_desired_state(
        {"stories": [{"action": "post_image", "asset_id": "story-missing"}]}
    )

    with pytest.raises(
        StoriesTdlibLiveDisabledError,
        match="^stories live TDLib execution is not enabled$",
    ):
        _policy(db_session).validate_job_creation(
            account=account,
            account_id=account.id,
            desired_state=desired_state,
            config=Settings(
                stories_enabled=True,
                profile_execution_adapter="tdlib",
                stories_tdlib_live_enabled=False,
                profile_job_cooldown_seconds=0,
            ),
        )


def test_profile_audio_title_is_trimmed_to_max_length(db_session) -> None:
    account = seed_account_with_profile(db_session)
    audio = seed_audio_asset(db_session)
    audio.original_filename = f"{'a' * 80}.mp3"
    db_session.commit()

    desired_state = _policy(db_session).normalize_desired_state_with_assets(
        account_id=account.id,
        desired_state={"profile_audio": {"action": "add", "audio_asset_id": audio.id}},
        workspace_id=account.workspace_id,
    )

    assert desired_state["profile_audio"]["title"] == "a" * 64


def test_profile_audio_validation_rejects_unsupported_format(db_session) -> None:
    account = seed_account_with_profile(db_session)
    audio = seed_audio_asset(db_session)
    audio.mime = "audio/ogg"
    db_session.commit()

    with pytest.raises(
        ProfileAudioUnsupportedFormatError,
        match="^profile audio must be MP3 or M4A$",
    ):
        _policy(db_session).normalize_desired_state_with_assets(
            account_id=account.id,
            desired_state={"profile_audio": {"action": "add", "audio_asset_id": audio.id}},
            workspace_id=account.workspace_id,
        )


def test_story_asset_validation_rejects_missing_asset(db_session) -> None:
    account = seed_account_with_profile(db_session)

    with pytest.raises(AccountAssetNotFoundError, match="^story asset not found$"):
        _policy(db_session).normalize_desired_state_with_assets(
            account_id=account.id,
            desired_state={
                "stories": [{"action": "post_image", "asset_id": "missing-story"}],
            },
            workspace_id=account.workspace_id,
        )


def test_story_asset_validation_rejects_wrong_asset_kind(db_session) -> None:
    account = seed_account_with_profile(db_session)
    audio = seed_audio_asset(db_session)
    audio.kind = AssetKind.PROFILE_AUDIO
    db_session.commit()

    with pytest.raises(AccountAssetKindInvalidError, match="^asset kind is not story_image$"):
        _policy(db_session).normalize_desired_state_with_assets(
            account_id=account.id,
            desired_state={
                "stories": [{"action": "post_image", "asset_id": audio.id}],
            },
            workspace_id=account.workspace_id,
        )
