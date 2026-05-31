from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from app.config import Settings, settings
from app.models import Account, AccountState, AssetKind, AssetStatus
from app.modules.account_editing.errors import (
    AccountAssetKindInvalidError,
    AccountAssetNotFoundError,
    AccountAssetNotReadyError,
    ProfileAudioUnsupportedFormatError,
    ProfileJobCooldownActiveError,
    StoriesDisabledError,
    StoriesTdlibLiveDisabledError,
)
from app.modules.account_editing.planner import (
    account_update_profile_payload,
    normalize_account_update_desired_state,
)
from app.modules.account_editing.repository import AccountEditingRepository
from app.modules.account_safety.interfaces import (
    build_account_safety_for_account,
    safety_preview_fields_with_policy,
    unique_preserve_order,
)
from app.services.asset_storage import materialize_asset_to_local_path
from app.services.assets import PROFILE_AUDIO_EXECUTION_MIMES
from app.services.auth import is_account_hard_stopped
from app.services.jobs import is_profile_job_cooldown_active


def _profile_name_changed(
    profile: dict[str, Any], profile_state: Any, requested_profile_fields: set[str]
) -> bool:
    if "name" not in requested_profile_fields:
        return False
    current_name = " ".join(
        part
        for part in [
            profile_state.first_name if profile_state else None,
            profile_state.last_name if profile_state else None,
        ]
        if part
    )
    return (profile.get("name") or "") != current_name


def _profile_text_changed(
    profile: dict[str, Any],
    profile_state: Any,
    requested_profile_fields: set[str],
    field_name: str,
) -> bool:
    if field_name not in requested_profile_fields:
        return False
    current_value = (getattr(profile_state, field_name) if profile_state else None) or ""
    return (profile.get(field_name) or "") != current_value


def _pinned_channel_changed(
    account: Account, profile: dict[str, Any], requested_profile_fields: set[str]
) -> bool:
    if "pinned_channel_ref" not in requested_profile_fields:
        return False
    desired_ref = profile.get("pinned_channel_ref") or ""
    current_ref = account.pinned_channel_ref or ""
    return desired_ref != current_ref


class AccountEditingPolicy:
    def __init__(self, session: Any) -> None:
        self._session = session
        self._repo = AccountEditingRepository(session)

    def normalize_desired_state_with_assets(
        self,
        *,
        account_id: str,
        desired_state: dict[str, Any],
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        desired_state = normalize_account_update_desired_state(desired_state)
        profile = cast(dict[str, Any], desired_state["profile"])
        profile_payload = self._repo.normalize_profile_payload(
            account_update_profile_payload(desired_state),
            workspace_id=workspace_id,
        )
        profile["photo_asset_path"] = profile_payload.get("photo_asset_path")
        self._validate_profile_audio_asset(
            account_id=account_id,
            desired_state=desired_state,
            workspace_id=workspace_id,
        )
        self._validate_story_assets(desired_state, workspace_id=workspace_id)
        return desired_state

    def preview_safety(
        self,
        *,
        account: Account,
        account_id: str,
        desired_state: dict[str, Any],
        config: Settings,
    ) -> tuple[list[str], list[str], dict[str, Any]]:
        blocking_errors: list[str] = []
        warnings: list[str] = []
        safety = build_account_safety_for_account(self._session, account, config=config)
        safety_fields = safety_preview_fields_with_policy(safety, desired_state, config=config)
        if is_account_hard_stopped(account):
            blocking_errors.append("account requires manual intervention")
        if account.account_state != AccountState.EXECUTION_USABLE:
            blocking_errors.append("account is not execution_usable")
        if is_profile_job_cooldown_active(self._session, account_id, config=config):
            blocking_errors.append("profile job cooldown active")
        if desired_state.get("stories") and not config.stories_enabled:
            blocking_errors.append("stories are disabled")
        if desired_state.get("stories") and self._stories_live_execution_blocked(config):
            blocking_errors.append("stories live TDLib execution is not enabled")
        blocking_errors.extend(self._invalid_channel_ref_errors(desired_state=desired_state))
        blocking_errors.extend(
            self._preview_blocking_safety_errors(safety_fields["safety_blockers"])
        )
        warnings.extend(safety_fields["safety_warnings"])
        return (
            unique_preserve_order(blocking_errors),
            unique_preserve_order(warnings),
            safety_fields,
        )

    def validate_job_creation(
        self,
        *,
        account: Account,
        account_id: str,
        desired_state: dict[str, Any],
        config: Settings,
    ) -> None:
        if is_profile_job_cooldown_active(self._session, account_id, config=config):
            raise ProfileJobCooldownActiveError()
        self._repo.check_workspace_job_limit(account.workspace_id)
        if desired_state.get("stories") and not config.stories_enabled:
            raise StoriesDisabledError()
        if desired_state.get("stories") and self._stories_live_execution_blocked(config):
            raise StoriesTdlibLiveDisabledError()
        safety = build_account_safety_for_account(self._session, account, config=config)
        safety_fields = safety_preview_fields_with_policy(safety, desired_state, config=config)
        create_blockers = self._create_job_safety_blockers(safety_fields["safety_blockers"])
        if create_blockers:
            raise ValueError(create_blockers[0])

    def requested_profile_fields(self, desired_state: dict[str, Any]) -> set[str]:
        profile = desired_state.get("profile")
        if not isinstance(profile, dict):
            return set()
        profile_payload = cast(dict[str, Any], profile)
        return set(profile_payload)

    def changed_profile_step_types(
        self,
        *,
        account: Account,
        desired_state: dict[str, Any],
        requested_profile_fields: set[str],
    ) -> set[str]:
        profile = cast(dict[str, Any], desired_state.get("profile") or {})
        profile_state = account.profile_state
        steps: set[str] = set()

        if _profile_name_changed(profile, profile_state, requested_profile_fields):
            steps.add("set_name")
        if _profile_text_changed(profile, profile_state, requested_profile_fields, "bio"):
            steps.add("set_bio")
        if _profile_text_changed(profile, profile_state, requested_profile_fields, "username"):
            steps.add("set_username")
        if self._profile_photo_changed(account, profile, requested_profile_fields):
            steps.add("set_profile_photo")
        if _pinned_channel_changed(account, profile, requested_profile_fields):
            steps.add("set_pinned_channel")

        return steps

    def _profile_photo_changed(
        self, account: Account, profile: dict[str, Any], requested_profile_fields: set[str]
    ) -> bool:
        if "photo_asset_id" not in requested_profile_fields:
            return False
        desired_photo_asset_id = profile.get("photo_asset_id")
        current_photo_asset_id = self._repo.latest_applied_profile_photo_asset_id(account.id)
        return bool(desired_photo_asset_id and desired_photo_asset_id != current_photo_asset_id)

    def _validate_profile_audio_asset(
        self,
        *,
        account_id: str,
        desired_state: dict[str, Any],
        workspace_id: str | None = None,
    ) -> None:
        profile_audio = cast(dict[str, Any], desired_state.get("profile_audio") or {})
        if profile_audio.get("action") == "remove":
            account = self._repo.get_account(account_id=account_id, workspace_id=workspace_id)
            if account and account.profile_audio_state:
                profile_audio["telegram_file_id"] = account.profile_audio_state.telegram_file_id
            return
        if profile_audio.get("action") != "add":
            return
        asset_id = profile_audio.get("audio_asset_id")
        asset = self._repo.get_asset(asset_id=asset_id, workspace_id=workspace_id)
        if asset is None:
            raise AccountAssetNotFoundError(
                field="profile_audio",
                legacy_message="audio asset not found",
            )
        if asset.kind != AssetKind.PROFILE_AUDIO:
            raise AccountAssetKindInvalidError(
                field="profile_audio",
                legacy_message="asset kind is not profile_audio",
            )
        if asset.status != AssetStatus.NORMALIZED:
            raise AccountAssetNotReadyError(
                field="profile_audio",
                legacy_message="asset is not ready for profile audio execution",
            )
        if asset.mime not in PROFILE_AUDIO_EXECUTION_MIMES:
            raise ProfileAudioUnsupportedFormatError()
        profile_audio["audio_asset_path"] = str(
            materialize_asset_to_local_path(asset, config=settings)
        )
        profile_audio["title"] = self._profile_audio_title(asset.original_filename)

    def _validate_story_assets(
        self, desired_state: dict[str, Any], *, workspace_id: str | None = None
    ) -> None:
        for story in cast(list[dict[str, Any]], desired_state.get("stories") or []):
            asset = self._repo.get_asset(asset_id=story.get("asset_id"), workspace_id=workspace_id)
            if asset is None:
                raise AccountAssetNotFoundError(
                    field="stories",
                    legacy_message="story asset not found",
                )
            expected_kind = (
                AssetKind.STORY_IMAGE
                if story.get("action") == "post_image"
                else AssetKind.STORY_VIDEO
            )
            if asset.kind != expected_kind:
                raise AccountAssetKindInvalidError(
                    field="photo_asset_id",
                    legacy_message=f"asset kind is not {expected_kind}",
                )
            if asset.status != AssetStatus.NORMALIZED:
                raise AccountAssetNotReadyError(
                    field="stories",
                    legacy_message="asset is not ready for story execution",
                )
            story["asset_path"] = str(materialize_asset_to_local_path(asset, config=settings))

    def _stories_live_execution_blocked(self, config: Settings) -> bool:
        return config.profile_execution_adapter == "tdlib" and not config.stories_tdlib_live_enabled

    def _create_job_safety_blockers(self, blockers: list[str]) -> list[str]:
        preview_only_capability_blockers = {
            "stories_mock_mode",
            "stories_live_disabled",
            "stories_disabled",
        }
        return [blocker for blocker in blockers if blocker not in preview_only_capability_blockers]

    def _preview_blocking_safety_errors(self, blockers: list[str]) -> list[str]:
        capability_only_blockers = {
            "stories_disabled",
            "stories_live_disabled",
            "stories_mock_mode",
        }
        return [blocker for blocker in blockers if blocker not in capability_only_blockers]

    # Phase 2.5 follow-up (#218 workspace-channels registry): once the
    # registry lands, this check must also reject channels not enrolled
    # for the workspace. Until then any well-formed @ref is accepted.
    def _invalid_channel_ref_errors(self, *, desired_state: dict[str, Any]) -> list[str]:
        profile = cast(dict[str, Any], desired_state.get("profile") or {})
        channel_ref = (profile.get("pinned_channel_ref") or "").strip()
        if not channel_ref:
            return []
        username_re = re.compile(r"^@[A-Za-z][A-Za-z0-9_]{3,31}$")
        numeric_re = re.compile(r"^-100\d+$")
        if username_re.match(channel_ref) or numeric_re.match(channel_ref):
            return []
        return ["invalid_channel_ref"]

    def _profile_audio_title(self, filename: str | None) -> str:
        if not filename:
            return ""
        title = Path(filename).stem.strip()
        return title[:64]
