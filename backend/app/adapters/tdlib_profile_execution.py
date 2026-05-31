from __future__ import annotations

from collections.abc import Iterator
import time
from typing import Any, Callable, cast

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibClient,
    TdlibClientFactory,
    extract_authorization_state,
    get_current_user_id,
    map_authorization_state,
    tdlib_parameters_query,
)
from app.adapters.tdlib_profile_audio import (
    _cleanup_temporary_profile_audio_message,
    _extract_message_audio_file,
    _tdlib_file_debug_payload,
    _tdlib_file_upload_completed,
    _tdlib_file_upload_ready_for_profile_audio,
    _upload_profile_audio_via_saved_messages,
    wait_for_tdlib_file_upload_completed,
)
from app.adapters.tdlib_profile_common import (
    TdlibProfileQueryError,
    _checked_send_query,
    _dict_or_empty,
    _profile_tdlib_error_code,
)
from app.adapters.tdlib_profile_pinned import _execute_set_pinned_channel
from app.adapters.tdlib_profile_steps import (
    _ProfileAudioState,
    _StepExecutionResult,
    _applied_step_result,
    _failed_pinned_channel_step_result,
    _failed_profile_step_result,
    _profile_audio_add_step_result,
    _profile_audio_remove_step_result,
    _profile_audio_upload_step_result,
    _story_post_step_result,
    _uncertain_username_step_result,
    _username_succeeded_step_result,
    _with_uploaded_profile_audio_id,
    classify_job_outcome,
    classify_step_outcome,
    map_step_to_tdlib_query,
    split_name,
    verify_username_result,
)
from app.adapters.tdlib_profile_story import (
    TdlibStoryPostUncertain,
    _can_post_story_error_code,
    _post_story,
    _story_content,
    _story_privacy_settings,
    _uncertain_story_step_result,
)
from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import AccountState, StepStatus
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib

__all__ = [
    "TdlibProfileExecutionAdapter",
    "UnavailableProfileExecutionAdapter",
    "TdlibProfileQueryError",
    "TdlibStoryPostUncertain",
    "build_profile_execution_adapter",
    "classify_job_outcome",
    "classify_step_outcome",
    "map_step_to_tdlib_query",
    "split_name",
    "verify_username_result",
    "wait_for_tdlib_file_upload_completed",
    "_can_post_story_error_code",
    "_dict_or_empty",
    "_extract_message_audio_file",
    "_profile_tdlib_error_code",
    "_story_content",
    "_story_privacy_settings",
    "_tdlib_file_debug_payload",
    "_tdlib_file_upload_completed",
    "_tdlib_file_upload_ready_for_profile_audio",
]


class TdlibProfileExecutionAdapter:
    def __init__(
        self,
        *,
        client_factory: TdlibClientFactory,
        config: Settings = settings,
        proxy_applier: Callable[[TdlibClient, str], bool] | None = None,
    ) -> None:
        self._client_factory = client_factory
        self._config = config
        self._proxy_applier = proxy_applier

    def inspect_runtime(self, account_id: str) -> dict[str, Any]:
        client = None
        try:
            client = self._client_factory.create(account_id)
            proxy_applied = False
            deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
            while time.monotonic() < deadline:
                event = client.receive(self._config.tdlib_receive_timeout_seconds)
                state = extract_authorization_state(event)
                if state is None:
                    continue
                mapped = map_authorization_state(state)
                if mapped.status.value == "wait_tdlib_parameters":
                    client.send(tdlib_parameters_query(self._config, account_id))
                    if self._proxy_applier is not None and not proxy_applied:
                        self._proxy_applier(client, account_id)
                        proxy_applied = True
                    continue
                if mapped.status.value == "ready":
                    return {
                        "ok": True,
                        "account_state": AccountState.EXECUTION_USABLE,
                        "runtime_health": "ready",
                        "telegram_user_id": get_current_user_id(client, self._config),
                        "error": None,
                    }
                return {
                    "ok": False,
                    "account_state": mapped.account_state,
                    "runtime_health": mapped.runtime_health,
                    "telegram_user_id": None,
                    "error": mapped.error,
                }
            return {
                "ok": False,
                "account_state": AccountState.RUNTIME_BROKEN,
                "runtime_health": "timeout",
                "telegram_user_id": None,
                "error": "TDLib runtime inspection timed out",
            }
        except Exception as exc:
            return {
                "ok": False,
                "account_state": AccountState.RUNTIME_BROKEN,
                "runtime_health": "broken",
                "telegram_user_id": None,
                "error": str(exc),
            }
        finally:
            if client is not None:
                client.close()

    def execute(
        self, account_id: str, plan_json_snapshot: dict[str, Any], payload_json: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        client = None
        try:
            client = self._client_factory.create(account_id)
            self._wait_until_ready(client, account_id)
            yield {"event": "runtime_started"}
            audio_state = _ProfileAudioState()
            for step in cast(list[dict[str, Any]], plan_json_snapshot["steps"]):
                event = {"step_key": step["step_key"], "step_type": step["step_type"]}
                yield {"event": "step_started", **event}
                result = self._execute_step(client, account_id, step, event, audio_state)
                yield from result.events
                if result.stop_runtime:
                    return
            yield {"event": "runtime_closed"}
        except Exception as exc:
            yield {
                "event": "runtime_failed",
                "error_code": "tdlib_runtime_failed",
                "error_class": exc.__class__.__name__,
                "error": str(exc),
            }
        finally:
            if client is not None:
                client.close()

    def _execute_step(
        self,
        client: TdlibClient,
        account_id: str,
        step: dict[str, Any],
        event: dict[str, Any],
        audio_state: _ProfileAudioState,
    ) -> _StepExecutionResult:
        try:
            return self._execute_step_inner(client, account_id, step, event, audio_state)
        except TdlibStoryPostUncertain as exc:
            return _uncertain_story_step_result(exc, event)
        except Exception as exc:
            return _failed_profile_step_result(exc, event)

    def _execute_step_inner(
        self,
        client: TdlibClient,
        account_id: str,
        step: dict[str, Any],
        event: dict[str, Any],
        audio_state: _ProfileAudioState,
    ) -> _StepExecutionResult:
        if step["step_type"] in {"post_story_image", "post_story_video"}:
            story_post = _post_story(client, step, self._config)
            return _story_post_step_result(story_post, event)

        step = _with_uploaded_profile_audio_id(step, audio_state)
        if step["step_type"] == "upload_profile_audio":
            return self._execute_profile_audio_upload(client, account_id, step, event, audio_state)
        if step["step_type"] == "set_pinned_channel":
            return self._execute_pinned_channel_step(client, step, event)

        response = _checked_send_query(
            client, map_step_to_tdlib_query(step), self._config.tdlib_auth_timeout_seconds
        )
        return self._query_step_result(client, account_id, step, event, response, audio_state)

    def _execute_profile_audio_upload(
        self,
        client: TdlibClient,
        account_id: str,
        step: dict[str, Any],
        event: dict[str, Any],
        audio_state: _ProfileAudioState,
    ) -> _StepExecutionResult:
        uploaded_file = _upload_profile_audio_via_saved_messages(
            client,
            step,
            self._config,
            account_id=account_id,
        )
        audio_state.file_id = int(uploaded_file["audio_file_id"])
        audio_state.temp_message = uploaded_file
        title = step["payload"].get("title")
        audio_state.title = str(title) if title else None
        return _profile_audio_upload_step_result(step, event, uploaded_file, audio_state.file_id)

    def _execute_pinned_channel_step(
        self, client: TdlibClient, step: dict[str, Any], event: dict[str, Any]
    ) -> _StepExecutionResult:
        pinned_result = _execute_set_pinned_channel(client, step, self._config)
        if pinned_result.get("failed"):
            return _failed_pinned_channel_step_result(event, pinned_result)
        return _applied_step_result(event, step)

    def _query_step_result(
        self,
        client: TdlibClient,
        account_id: str,
        step: dict[str, Any],
        event: dict[str, Any],
        response: dict[str, Any],
        audio_state: _ProfileAudioState,
    ) -> _StepExecutionResult:
        if step["step_type"] == "add_profile_audio":
            self._log_profile_audio_add_response(account_id, step, response)
            self._cleanup_profile_audio_temp_message(client, account_id, step, audio_state)
            return _profile_audio_add_step_result(step, event, audio_state)
        if step["step_type"] == "remove_profile_audio":
            return _profile_audio_remove_step_result(event)
        if step["step_type"] in {"validate_story_capabilities", "prepare_story_media"}:
            return _applied_step_result(event, step)
        if step["step_type"] == "set_username":
            return self._username_step_result(client, step, event)
        return _applied_step_result(event, step)

    def _log_profile_audio_add_response(
        self, account_id: str, step: dict[str, Any], response: dict[str, Any]
    ) -> None:
        log_event(
            "tdlib_profile_audio_add_response",
            account_id=account_id,
            step_key=step["step_key"],
            audio_asset_id=step["payload"].get("audio_asset_id"),
            telegram_file_id=step["payload"].get("telegram_file_id"),
            response_type=response.get("@type"),
        )

    def _cleanup_profile_audio_temp_message(
        self,
        client: TdlibClient,
        account_id: str,
        step: dict[str, Any],
        audio_state: _ProfileAudioState,
    ) -> None:
        if audio_state.temp_message is None:
            return
        _cleanup_temporary_profile_audio_message(
            client,
            audio_state.temp_message,
            self._config,
            account_id=account_id,
            step_key=str(step["step_key"]),
        )

    def _username_step_result(
        self, client: TdlibClient, step: dict[str, Any], event: dict[str, Any]
    ) -> _StepExecutionResult:
        me = _checked_send_query(
            client, {"@type": "getMe"}, self._config.tdlib_receive_timeout_seconds
        )
        verification = verify_username_result(str(step["payload"].get("username") or ""), me)
        if verification["status"] == StepStatus.UNCERTAIN:
            return _uncertain_username_step_result(event, verification)
        return _username_succeeded_step_result(event, step, verification)

    def _wait_until_ready(self, client: TdlibClient, account_id: str) -> None:
        proxy_applied = False
        deadline = time.monotonic() + self._config.tdlib_auth_timeout_seconds
        while time.monotonic() < deadline:
            event = client.receive(self._config.tdlib_receive_timeout_seconds)
            state = extract_authorization_state(event)
            if state is None:
                continue
            mapped = map_authorization_state(state)
            if mapped.status.value == "wait_tdlib_parameters":
                client.send(tdlib_parameters_query(self._config, account_id))
                if self._proxy_applier is not None and not proxy_applied:
                    self._proxy_applier(client, account_id)
                    proxy_applied = True
                continue
            if mapped.status.value == "ready":
                return
            raise RuntimeError(mapped.error or mapped.runtime_health)
        raise TimeoutError("TDLib runtime readiness timed out")


def build_profile_execution_adapter(config: Settings = settings):
    if config.profile_execution_adapter == "tdlib":
        try:
            return TdlibProfileExecutionAdapter(
                client_factory=RealTdJsonClientFactory(config.tdlib_shared_library_path),
                config=config,
                proxy_applier=lambda client, account_id: apply_account_proxy_to_tdlib(
                    client, account_id, config=config
                ),
            )
        except OSError as exc:
            return UnavailableProfileExecutionAdapter(str(exc))
    from app.adapters.profile_execution import MockProfileExecutionAdapter

    return MockProfileExecutionAdapter()


class UnavailableProfileExecutionAdapter:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def inspect_runtime(self, account_id: str) -> dict[str, Any]:
        return {
            "ok": False,
            "account_state": AccountState.RUNTIME_BROKEN,
            "runtime_health": "tdlib_unavailable",
            "telegram_user_id": None,
            "error": self._reason,
        }

    def execute(
        self, account_id: str, plan_json_snapshot: dict[str, Any], payload_json: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        yield {
            "event": "runtime_failed",
            "error_class": "TdlibUnavailable",
            "error_code": "TDLIB_UNAVAILABLE",
        }
