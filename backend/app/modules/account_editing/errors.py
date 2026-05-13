from __future__ import annotations


class AccountEditingError(ValueError):
    """Base typed domain error for account editing."""

    def __init__(
        self,
        legacy_message: str,
        error_code: str = "VALIDATION_ERROR",
        error_class: str = "validation",
        field_errors: tuple[dict[str, str], ...] = (),
    ) -> None:
        super().__init__(legacy_message)
        self.legacy_message = legacy_message
        self.error_code = error_code
        self.error_class = error_class
        self.field_errors = field_errors

    def __str__(self) -> str:
        return self.legacy_message

    def to_value_error(self) -> ValueError:
        return ValueError(self.legacy_message)


class AccountNotFoundError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="account not found",
            error_code="ACCOUNT_NOT_FOUND",
            error_class="not_found",
        )


class AccountManualInterventionRequiredError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="account requires manual intervention",
            error_code="ACCOUNT_MANUAL_INTERVENTION_REQUIRED",
            error_class="runtime",
        )


class AccountRuntimeUnusableError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="account is not execution_usable",
            error_code="RUNTIME_UNUSABLE",
            error_class="runtime",
        )


class ProfileJobCooldownActiveError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="profile job cooldown active",
            error_code="PROFILE_JOB_COOLDOWN_ACTIVE",
            error_class="rate_limit",
        )


class AccountAssetNotFoundError(AccountEditingError):
    def __init__(
        self,
        *,
        field: str = "photo_asset_id",
        legacy_message: str = "asset not found",
    ) -> None:
        error_code = (
            "STORY_ASSET_NOT_READY"
            if "story" in legacy_message and "asset" in legacy_message
            else "VALIDATION_ERROR"
        )
        super().__init__(
            legacy_message=legacy_message,
            error_code=error_code,
            field_errors=({"field": field, "message": legacy_message},),
        )


class AccountAssetKindInvalidError(AccountEditingError):
    def __init__(
        self,
        *,
        field: str = "photo_asset_id",
        legacy_message: str = "asset kind is not profile_photo",
    ) -> None:
        super().__init__(
            legacy_message=legacy_message,
            field_errors=({"field": field, "message": legacy_message},),
        )


class AccountAssetNotReadyError(AccountEditingError):
    def __init__(
        self,
        *,
        field: str = "photo_asset_id",
        legacy_message: str = "asset is not ready for profile photo execution",
    ) -> None:
        error_code = (
            "STORY_ASSET_NOT_READY"
            if "story" in legacy_message and "asset" in legacy_message
            else "VALIDATION_ERROR"
        )
        super().__init__(
            legacy_message=legacy_message,
            error_code=error_code,
            field_errors=({"field": field, "message": legacy_message},),
        )


class ProfileAudioUnsupportedFormatError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="profile audio must be MP3 or M4A",
            error_code="PROFILE_AUDIO_UNSUPPORTED_FORMAT",
            field_errors=(
                {"field": "profile_audio", "message": "profile audio must be MP3 or M4A"},
            ),
        )


class StoriesDisabledError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="stories are disabled",
            error_code="STORIES_DISABLED",
            error_class="capability",
        )


class StoriesTdlibLiveDisabledError(AccountEditingError):
    def __init__(self) -> None:
        super().__init__(
            legacy_message="stories live TDLib execution is not enabled",
            error_code="STORIES_TDLIB_LIVE_DISABLED",
            error_class="capability",
        )


def account_editing_error_from_legacy_message(message: str) -> AccountEditingError | None:
    if message == "account not found":
        return AccountNotFoundError()
    if message == "account requires manual intervention":
        return AccountManualInterventionRequiredError()
    if message == "account is not execution_usable":
        return AccountRuntimeUnusableError()
    if message == "profile job cooldown active":
        return ProfileJobCooldownActiveError()
    if message == "asset not found":
        return AccountAssetNotFoundError()
    if message == "asset kind is not profile_photo":
        return AccountAssetKindInvalidError()
    if message == "asset is not ready for profile photo execution":
        return AccountAssetNotReadyError()
    if message == "profile audio must be MP3 or M4A":
        return ProfileAudioUnsupportedFormatError()
    if message == "stories are disabled":
        return StoriesDisabledError()
    if message == "stories live TDLib execution is not enabled":
        return StoriesTdlibLiveDisabledError()
    return None
