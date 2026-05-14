from __future__ import annotations

# test-analyzer: disable-file=STG007 reason="checks typed error metadata, not rate-limit counters"

from app.modules.account_editing.errors import (
    AccountAssetKindInvalidError,
    AccountAssetNotFoundError,
    AccountAssetNotReadyError,
    AccountManualInterventionRequiredError,
    AccountNotFoundError,
    AccountRuntimeUnusableError,
    ProfileAudioUnsupportedFormatError,
    ProfileJobCooldownActiveError,
    StoriesDisabledError,
    StoriesTdlibLiveDisabledError,
)


def test_account_not_found_error_preserves_legacy_message_and_metadata() -> None:
    error = AccountNotFoundError()

    assert str(error) == "account not found"
    assert error.error_code == "ACCOUNT_NOT_FOUND"
    assert error.error_class == "not_found"
    assert str(error.to_value_error()) == "account not found"


def test_runtime_errors_preserve_legacy_messages_and_metadata() -> None:
    manual = AccountManualInterventionRequiredError()
    unusable = AccountRuntimeUnusableError()
    cooldown = ProfileJobCooldownActiveError()

    assert str(manual) == "account requires manual intervention"
    assert manual.error_code == "ACCOUNT_MANUAL_INTERVENTION_REQUIRED"
    assert manual.error_class == "runtime"
    assert str(unusable) == "account is not execution_usable"
    assert unusable.error_code == "RUNTIME_UNUSABLE"
    assert unusable.error_class == "runtime"
    assert str(cooldown) == "profile job cooldown active"
    assert cooldown.error_code == "PROFILE_JOB_COOLDOWN_ACTIVE"
    assert cooldown.error_class == "rate_limit"


def test_asset_errors_preserve_legacy_messages_and_field_metadata() -> None:
    missing = AccountAssetNotFoundError()
    invalid = AccountAssetKindInvalidError()
    not_ready = AccountAssetNotReadyError()

    assert str(missing) == "asset not found"
    assert missing.field_errors == ({"field": "photo_asset_id", "message": "asset not found"},)
    assert str(invalid) == "asset kind is not profile_photo"
    assert invalid.field_errors == (
        {"field": "photo_asset_id", "message": "asset kind is not profile_photo"},
    )
    assert str(not_ready) == "asset is not ready for profile photo execution"
    assert not_ready.field_errors == (
        {
            "field": "photo_asset_id",
            "message": "asset is not ready for profile photo execution",
        },
    )


def test_profile_audio_error_preserves_legacy_message_and_field_metadata() -> None:
    error = ProfileAudioUnsupportedFormatError()

    assert str(error) == "profile audio must be MP3 or M4A"
    assert error.error_code == "PROFILE_AUDIO_UNSUPPORTED_FORMAT"
    assert error.field_errors == (
        {"field": "profile_audio", "message": "profile audio must be MP3 or M4A"},
    )


def test_story_capability_errors_preserve_legacy_messages_and_metadata() -> None:
    disabled = StoriesDisabledError()
    live_disabled = StoriesTdlibLiveDisabledError()

    assert str(disabled) == "stories are disabled"
    assert disabled.error_code == "STORIES_DISABLED"
    assert disabled.error_class == "capability"
    assert str(live_disabled) == "stories live TDLib execution is not enabled"
    assert live_disabled.error_code == "STORIES_TDLIB_LIVE_DISABLED"
    assert live_disabled.error_class == "capability"
