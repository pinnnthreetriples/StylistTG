from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import time
from typing import Any, Callable, cast

from app.adapters.tdlib_auth import (
    RealTdJsonClientFactory,
    TdlibClient,
    TdlibClientFactory,
    extract_authorization_state,
    get_current_user_id,
    map_authorization_state,
    map_tdlib_error,
    tdlib_parameters_query,
)
from app.config import Settings, settings
from app.logging_utils import log_event
from app.models import AccountState, JobState, StepStatus
from app.services.tdlib_proxy import apply_account_proxy_to_tdlib


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def split_name(full_name: str | None) -> tuple[str, str]:
    normalized = (full_name or "").strip()
    if not normalized:
        return "", ""
    parts = normalized.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _query_set_name(payload: dict[str, Any]) -> dict[str, Any]:
    first_name = payload.get("first_name")
    last_name = payload.get("last_name")
    if first_name is None and last_name is None:
        first_name, last_name = split_name(payload.get("name"))
    return {"@type": "setName", "first_name": first_name or "", "last_name": last_name or ""}


def _query_set_bio(payload: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "setBio", "bio": payload.get("bio") or ""}


def _query_set_username(payload: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "setUsername", "username": payload.get("username") or ""}


def _query_set_pinned_channel(payload: dict[str, Any]) -> dict[str, Any]:
    channel_ref = payload.get("pinned_channel_ref") or ""
    if not channel_ref:
        return {"@type": "setPersonalChat", "chat_id": 0}
    if channel_ref.startswith("@"):
        return {"@type": "searchPublicChat", "username": channel_ref.lstrip("@")}
    if channel_ref.lstrip("-").isdigit():
        return {"@type": "setPersonalChat", "chat_id": int(channel_ref)}
    return {"@type": "setPersonalChat", "chat_id": 0}


def _query_set_profile_photo(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "@type": "setProfilePhoto",
        "photo": {
            "@type": "inputChatPhotoStatic",
            "photo": {
                "@type": "inputFileLocal",
                "path": payload["asset_path"],
            },
        },
        "is_public": False,
    }


def _query_add_profile_audio(payload: dict[str, Any]) -> dict[str, Any]:
    file_id = payload.get("telegram_file_id")
    if file_id is None:
        raise ValueError("telegram_file_id is required for add_profile_audio")
    return {"@type": "addProfileAudio", "file_id": int(file_id)}


def _query_remove_profile_audio(payload: dict[str, Any]) -> dict[str, Any]:
    file_id = payload.get("telegram_file_id")
    if file_id is None:
        return {"@type": "getMe"}
    return {"@type": "removeProfileAudio", "file_id": int(file_id)}


def _query_get_me(_payload: dict[str, Any]) -> dict[str, Any]:
    return {"@type": "getMe"}


_STEP_QUERY_BUILDERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "set_name": _query_set_name,
    "set_bio": _query_set_bio,
    "set_username": _query_set_username,
    "set_pinned_channel": _query_set_pinned_channel,
    "set_profile_photo": _query_set_profile_photo,
    "add_profile_audio": _query_add_profile_audio,
    "remove_profile_audio": _query_remove_profile_audio,
    "validate_story_capabilities": _query_get_me,
    "prepare_story_media": _query_get_me,
}


def map_step_to_tdlib_query(step: dict[str, Any]) -> dict[str, Any]:
    step_type = step["step_type"]
    payload = step["payload"]
    query_builder = _STEP_QUERY_BUILDERS.get(step_type)
    if query_builder is not None:
        return query_builder(payload)
    raise ValueError(f"Unsupported profile step type: {step_type}")


def verify_username_result(desired_username: str, me_response: dict[str, Any]) -> dict[str, Any]:
    usernames = _dict_or_empty(me_response.get("usernames"))
    active_value = usernames.get("active_usernames")
    active = cast(list[Any], active_value) if isinstance(active_value, list) else []
    editable = usernames.get("editable_username")
    matched = desired_username == editable or desired_username in active
    if matched:
        return {
            "status": StepStatus.SUCCEEDED,
            "verification_attempted": True,
            "verification_result": {"editable_username": editable, "active_usernames": active},
            "uncertain_reason": None,
        }
    return {
        "status": StepStatus.UNCERTAIN,
        "verification_attempted": True,
        "verification_result": {"editable_username": editable, "active_usernames": active},
        "uncertain_reason": "username_verify_mismatch",
        "result_payload": {"desired_username": desired_username},
    }


def classify_step_outcome(step_type: str, outcome: str) -> StepStatus:
    if outcome == "uncertain":
        return StepStatus.UNCERTAIN
    if outcome == "failed":
        return StepStatus.FAILED
    return StepStatus.SUCCEEDED


def classify_job_outcome(step_results: list[dict[str, Any]]) -> JobState:
    statuses = {result["status"] for result in step_results}
    if StepStatus.FAILED in statuses:
        return JobState.FAILED
    if any(
        result["status"] == StepStatus.UNCERTAIN and result["step_type"] == "set_username"
        for result in step_results
    ):
        return JobState.MANUAL_INTERVENTION_NEEDED
    if StepStatus.UNCERTAIN in statuses:
        return JobState.PARTIALLY_COMPLETED
    return JobState.COMPLETED


@dataclass
class _ProfileAudioState:
    file_id: int | None = None
    temp_message: dict[str, Any] | None = None
    title: str | None = None


@dataclass(frozen=True)
class _StepExecutionResult:
    events: list[dict[str, Any]]
    stop_runtime: bool = False


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


def _with_uploaded_profile_audio_id(
    step: dict[str, Any], audio_state: _ProfileAudioState
) -> dict[str, Any]:
    if step["step_type"] != "add_profile_audio" or audio_state.file_id is None:
        return step
    return {
        **step,
        "payload": {
            **step["payload"],
            "telegram_file_id": audio_state.file_id,
        },
    }


def _story_post_step_result(
    story_post: dict[str, Any], event: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": True,
                "verification_result": {
                    "telegram_story_id": story_post["telegram_story_id"],
                    "status": story_post["status"],
                },
                "result_payload": {"story_post": story_post},
            }
        ]
    )


def _profile_audio_upload_step_result(
    step: dict[str, Any],
    event: dict[str, Any],
    uploaded_file: dict[str, Any],
    file_id: int,
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {
                    "audio_asset_id": step["payload"].get("audio_asset_id"),
                    "telegram_file_id": str(file_id),
                    "temporary_message_id": str(uploaded_file.get("message_id") or ""),
                },
            }
        ]
    )


def _failed_pinned_channel_step_result(
    event: dict[str, Any], pinned_result: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_failed",
                **event,
                "error_code": pinned_result["error_code"],
                "error_class": "PinnedChannelResolutionError",
                "result_payload": {
                    "message": pinned_result["error_message"],
                },
            },
            {
                "event": "runtime_failed",
                "error_class": "PinnedChannelResolutionError",
                "error_code": pinned_result["error_code"],
            },
        ],
        stop_runtime=True,
    )


def _applied_step_result(event: dict[str, Any], step: dict[str, Any]) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {"applied": step["payload"]},
            }
        ]
    )


def _profile_audio_add_step_result(
    step: dict[str, Any], event: dict[str, Any], audio_state: _ProfileAudioState
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {
                    "profile_audio": {
                        "source_asset_id": step["payload"].get("audio_asset_id"),
                        "telegram_file_id": str(audio_state.file_id),
                        "title": audio_state.title,
                        "performer": None,
                        "duration_seconds": None,
                        "mime": None,
                    }
                },
            }
        ]
    )


def _profile_audio_remove_step_result(event: dict[str, Any]) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": False,
                "verification_result": None,
                "result_payload": {"profile_audio_removed": True},
            }
        ]
    )


def _uncertain_username_step_result(
    event: dict[str, Any], verification: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_uncertain",
                **event,
                "verification_attempted": True,
                "verification_result": verification["verification_result"],
                "uncertain_reason": verification["uncertain_reason"],
                "result_payload": verification["result_payload"],
            },
            {"event": "runtime_closed"},
        ],
        stop_runtime=True,
    )


def _username_succeeded_step_result(
    event: dict[str, Any], step: dict[str, Any], verification: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_succeeded",
                **event,
                "verification_attempted": True,
                "verification_result": verification["verification_result"],
                "result_payload": {"applied": step["payload"]},
            }
        ]
    )


def _uncertain_story_step_result(
    exc: TdlibStoryPostUncertain, event: dict[str, Any]
) -> _StepExecutionResult:
    return _StepExecutionResult(
        events=[
            {
                "event": "step_uncertain",
                **event,
                "verification_attempted": True,
                "verification_result": exc.verification_result,
                "uncertain_reason": exc.uncertain_reason,
                "result_payload": exc.result_payload,
            },
            {"event": "runtime_closed"},
        ],
        stop_runtime=True,
    )


def _failed_profile_step_result(exc: Exception, event: dict[str, Any]) -> _StepExecutionResult:
    error_code = getattr(exc, "error_code", "tdlib_profile_step_failed")
    return _StepExecutionResult(
        events=[
            {
                "event": "step_failed",
                **event,
                "error_code": error_code,
                "error_class": exc.__class__.__name__,
                "result_payload": {"message": str(exc)},
            },
            {
                "event": "runtime_failed",
                "error_class": exc.__class__.__name__,
                "error_code": error_code,
            },
        ],
        stop_runtime=True,
    )


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


class TdlibProfileQueryError(RuntimeError):
    def __init__(self, message: str, *, error_code: str) -> None:
        super().__init__(message)
        self.error_code = error_code


class TdlibStoryPostUncertain(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        uncertain_reason: str,
        verification_result: dict[str, Any],
        result_payload: dict[str, Any],
    ) -> None:
        super().__init__(message)
        self.uncertain_reason = uncertain_reason
        self.verification_result = verification_result
        self.result_payload = result_payload


def _checked_send_query(
    client: TdlibClient, query: dict[str, Any], timeout_seconds: float
) -> dict[str, Any]:
    response = client.send_query(query, timeout_seconds)
    if response.get("@type") != "error":
        return response
    mapped = map_tdlib_error(response)
    error_code = _profile_tdlib_error_code(response, mapped.recovery_marker)
    raise TdlibProfileQueryError(mapped.error or "TDLib query failed", error_code=error_code)


def _execute_set_pinned_channel(
    client: TdlibClient, step: dict[str, Any], config: Settings
) -> dict[str, Any]:
    payload = step["payload"]
    channel_ref = (payload.get("pinned_channel_ref") or "").strip()
    if not channel_ref:
        _checked_send_query(
            client, {"@type": "setPersonalChat", "chat_id": 0}, config.tdlib_auth_timeout_seconds
        )
        return {"ok": True}
    if channel_ref.startswith("@"):
        username = channel_ref.lstrip("@")
        if not username:
            return {
                "failed": True,
                "error_code": "invalid_channel_ref",
                "error_message": "empty username after @",
            }
        search_query = {"@type": "searchPublicChat", "username": username}
        search_response = client.send_query(search_query, config.tdlib_auth_timeout_seconds)
        if search_response.get("@type") == "error" or search_response.get("@type") != "chat":
            return {
                "failed": True,
                "error_code": "pinned_channel_not_found",
                "error_message": f"channel {channel_ref} not found",
            }
        chat_id = search_response.get("id")
        if not chat_id:
            return {
                "failed": True,
                "error_code": "pinned_channel_not_found",
                "error_message": f"channel {channel_ref} not found",
            }
        _checked_send_query(
            client,
            {"@type": "setPersonalChat", "chat_id": int(chat_id)},
            config.tdlib_auth_timeout_seconds,
        )
        return {"ok": True}
    if channel_ref.lstrip("-").isdigit():
        _checked_send_query(
            client,
            {"@type": "setPersonalChat", "chat_id": int(channel_ref)},
            config.tdlib_auth_timeout_seconds,
        )
        return {"ok": True}
    return {
        "failed": True,
        "error_code": "invalid_channel_ref",
        "error_message": f"invalid channel reference: {channel_ref}",
    }


def _profile_tdlib_error_code(response: dict[str, Any], recovery_marker: str | None) -> str:
    message = str(response.get("message") or "").strip().upper()
    if message.startswith(("USERNAME_", "FLOOD_", "FROZEN_")):
        return message
    return (recovery_marker or "tdlib_profile_step_failed").removeprefix("tdlib_hard_stop:")


def _tdlib_file_upload_completed(response: dict[str, Any]) -> bool:
    remote = _dict_or_empty(response.get("remote"))
    if not remote:
        return False
    return remote.get("is_uploading_completed") is True


def _tdlib_file_upload_ready_for_profile_audio(response: dict[str, Any]) -> bool:
    if _tdlib_file_upload_completed(response):
        return True
    remote = _dict_or_empty(response.get("remote"))
    if not remote or remote.get("is_uploading_active") is not False:
        return False
    uploaded_size = remote.get("uploaded_size")
    expected_size = response.get("expected_size") or response.get("size")
    if not isinstance(uploaded_size, int) or not isinstance(expected_size, int):
        return False
    return expected_size > 0 and uploaded_size >= expected_size


def _tdlib_file_debug_payload(file_obj: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(file_obj, dict):
        return {}
    remote = _dict_or_empty(file_obj.get("remote"))
    local = _dict_or_empty(file_obj.get("local"))
    payload: dict[str, Any] = {
        "id": file_obj.get("id"),
        "size": file_obj.get("size"),
        "expected_size": file_obj.get("expected_size"),
    }
    if remote:
        payload["remote"] = {
            "is_uploading_active": remote.get("is_uploading_active"),
            "is_uploading_completed": remote.get("is_uploading_completed"),
            "uploaded_size": remote.get("uploaded_size"),
            "has_id": bool(remote.get("id")),
            "has_unique_id": bool(remote.get("unique_id")),
        }
    if local:
        payload["local"] = {
            "is_downloading_completed": local.get("is_downloading_completed"),
            "downloaded_prefix_size": local.get("downloaded_prefix_size"),
        }
    return payload


def wait_for_tdlib_file_upload_completed(
    client: TdlibClient,
    file_response: dict[str, Any],
    timeout_seconds: float,
    receive_timeout_seconds: float,
    *,
    account_id: str | None = None,
    step_key: str | None = None,
    audio_asset_id: str | None = None,
) -> dict[str, Any] | None:
    file_id = file_response.get("id")
    if _tdlib_file_upload_ready_for_profile_audio(file_response):
        return file_response
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        event = client.receive(min(receive_timeout_seconds, max(deadline - time.monotonic(), 0.0)))
        if event is None:
            continue
        if event.get("@type") != "updateFile":
            continue
        updated_file = _dict_or_empty(event.get("file"))
        if not updated_file or updated_file.get("id") != file_id:
            continue
        log_event(
            "tdlib_profile_audio_update_file",
            account_id=account_id,
            step_key=step_key,
            audio_asset_id=audio_asset_id,
            file=_tdlib_file_debug_payload(updated_file),
        )
        if _tdlib_file_upload_ready_for_profile_audio(updated_file):
            return updated_file
    return None


def _upload_profile_audio_via_saved_messages(
    client: TdlibClient,
    step: dict[str, Any],
    config: Settings,
    *,
    account_id: str,
) -> dict[str, Any]:
    payload = step["payload"]
    chat_id = _get_saved_messages_chat_id(client, config)
    message = _checked_send_query(
        client,
        {
            "@type": "sendMessage",
            "chat_id": chat_id,
            "input_message_content": {
                "@type": "inputMessageAudio",
                "audio": {"@type": "inputFileLocal", "path": payload["asset_path"]},
                "album_cover_thumbnail": None,
                "duration": 0,
                "title": payload.get("title") or "",
                "performer": "",
                "caption": {"@type": "formattedText", "text": "", "entities": []},
            },
        },
        config.tdlib_auth_timeout_seconds,
    )
    final_message = _wait_for_audio_message_send_succeeded(
        client,
        chat_id=chat_id,
        old_message_id=int(message.get("id") or 0),
        config=config,
        account_id=account_id,
        step_key=step["step_key"],
        audio_asset_id=payload.get("audio_asset_id"),
    )
    audio_file = _extract_message_audio_file(final_message)
    audio_file_id = audio_file.get("id")
    if audio_file_id is None:
        raise TdlibProfileQueryError(
            "Telegram sent the audio message, but did not return an audio file identifier",
            error_code="PROFILE_AUDIO_FILE_ID_MISSING",
        )
    log_event(
        "tdlib_profile_audio_saved_message_ready",
        account_id=account_id,
        step_key=step["step_key"],
        audio_asset_id=payload.get("audio_asset_id"),
        chat_id=chat_id,
        message_id=final_message.get("id"),
        file=_tdlib_file_debug_payload(audio_file),
    )
    return {
        "audio_file_id": int(audio_file_id),
        "chat_id": chat_id,
        "message_id": final_message.get("id"),
    }


def _wait_for_audio_message_send_succeeded(
    client: TdlibClient,
    *,
    chat_id: int,
    old_message_id: int,
    config: Settings,
    account_id: str,
    step_key: str,
    audio_asset_id: str | None,
) -> dict[str, Any]:
    deadline = time.monotonic() + config.tdlib_auth_timeout_seconds
    while time.monotonic() < deadline:
        event = client.receive(config.tdlib_receive_timeout_seconds)
        if event is None:
            continue
        event_type = event.get("@type")
        if (
            event_type == "updateMessageSendSucceeded"
            and event.get("old_message_id") == old_message_id
        ):
            message = _dict_or_empty(event.get("message"))
            if message:
                return message
        if (
            event_type == "updateMessageSendFailed"
            and event.get("old_message_id") == old_message_id
        ):
            log_event(
                "tdlib_profile_audio_saved_message_failed",
                account_id=account_id,
                step_key=step_key,
                audio_asset_id=audio_asset_id,
                chat_id=chat_id,
                old_message_id=old_message_id,
                error_code=event.get("error_code"),
                error_message=event.get("error_message"),
            )
            raise TdlibProfileQueryError(
                str(event.get("error_message") or "Telegram did not send the audio message"),
                error_code="PROFILE_AUDIO_MESSAGE_SEND_FAILED",
            )
    raise TdlibProfileQueryError(
        "Telegram did not confirm the temporary audio message",
        error_code="PROFILE_AUDIO_MESSAGE_SEND_TIMEOUT",
    )


def _extract_message_audio_file(message: dict[str, Any]) -> dict[str, Any]:
    content = _dict_or_empty(message.get("content"))
    if content.get("@type") != "messageAudio":
        return {}
    audio = _dict_or_empty(content.get("audio"))
    if not audio:
        return {}
    audio_file = _dict_or_empty(audio.get("audio"))
    if not audio_file:
        return {}
    return audio_file


def _cleanup_temporary_profile_audio_message(
    client: TdlibClient,
    temporary_message: dict[str, Any],
    config: Settings,
    *,
    account_id: str,
    step_key: str,
) -> None:
    chat_id = temporary_message.get("chat_id")
    message_id = temporary_message.get("message_id")
    if chat_id is None or message_id is None:
        return
    try:
        _checked_send_query(
            client,
            {
                "@type": "deleteMessages",
                "chat_id": int(chat_id),
                "message_ids": [int(message_id)],
                "revoke": True,
            },
            config.tdlib_receive_timeout_seconds,
        )
    except Exception as exc:
        log_event(
            "tdlib_profile_audio_temp_message_cleanup_failed",
            account_id=account_id,
            step_key=step_key,
            chat_id=chat_id,
            message_id=message_id,
            error_class=exc.__class__.__name__,
            error_message=str(exc),
        )


def _post_story(client: TdlibClient, step: dict[str, Any], config: Settings) -> dict[str, Any]:
    payload = step["payload"]
    media_kind = "image" if step["step_type"] == "post_story_image" else "video"
    chat_id = _get_saved_messages_chat_id(client, config)
    _ensure_can_post_story(client, chat_id, config)
    temporary_story = _checked_send_query(
        client,
        {
            "@type": "postStory",
            "chat_id": chat_id,
            "content": _story_content(media_kind, payload["asset_path"]),
            "areas": {"@type": "inputStoryAreas", "areas": []},
            "caption": {
                "@type": "formattedText",
                "text": payload.get("caption") or "",
                "entities": [],
            },
            "privacy_settings": _story_privacy_settings(payload.get("privacy_preset")),
            "album_ids": [],
            "active_period": int(payload.get("active_period_seconds") or 86400),
            "from_story_full_id": None,
            "is_posted_to_chat_page": False,
            "protect_content": bool(payload.get("protect_content")),
        },
        config.tdlib_auth_timeout_seconds,
    )
    temporary_story_id = temporary_story.get("id")
    if temporary_story_id is None:
        raise TdlibProfileQueryError(
            "TDLib postStory did not return temporary story id",
            error_code="STORY_POST_TEMPORARY_ID_MISSING",
        )
    final_story = _wait_for_story_post_confirmation(client, int(temporary_story_id), config)
    story_id = str(final_story.get("id") or "")
    return {
        "asset_id": payload.get("asset_id"),
        "media_kind": media_kind,
        "caption": payload.get("caption") or "",
        "privacy_preset": payload.get("privacy_preset") or "contacts",
        "active_period_seconds": int(payload.get("active_period_seconds") or 86400),
        "protect_content": bool(payload.get("protect_content")),
        "telegram_story_id": story_id,
        "temporary_story_id": str(temporary_story_id or ""),
        "status": "posted",
        "raw_tdlib_json": final_story,
    }


def _story_content(media_kind: str, asset_path: str) -> dict[str, Any]:
    if media_kind == "image":
        return {
            "@type": "inputStoryContentPhoto",
            "photo": {"@type": "inputFileLocal", "path": asset_path},
            "added_sticker_file_ids": [],
        }
    return {
        "@type": "inputStoryContentVideo",
        "video": {"@type": "inputFileLocal", "path": asset_path},
        "added_sticker_file_ids": [],
        "duration": 0,
        "cover_frame_timestamp": 0,
        "is_animation": False,
    }


def _wait_for_story_post_confirmation(
    client: TdlibClient, temporary_story_id: int, config: Settings
) -> dict[str, Any]:
    deadline = time.monotonic() + min(config.tdlib_auth_timeout_seconds, 30.0)
    while time.monotonic() < deadline:
        event = client.receive(config.tdlib_receive_timeout_seconds)
        if event is None:
            continue
        event_type = event.get("@type")
        if (
            event_type == "updateStoryPostSucceeded"
            and event.get("old_story_id") == temporary_story_id
        ):
            story = _dict_or_empty(event.get("story"))
            if story:
                return story
        if event_type == "updateStoryPostFailed":
            story = _dict_or_empty(event.get("story"))
            if story.get("id") == temporary_story_id:
                error = _dict_or_empty(event.get("error"))
                raise TdlibProfileQueryError(
                    str(error.get("message") or "TDLib story post failed"),
                    error_code=str(error.get("message") or "STORY_POST_FAILED"),
                )
    temporary_payload = {
        "story_post": {
            "temporary_story_id": str(temporary_story_id),
            "telegram_story_id": None,
            "status": "posting",
        }
    }
    raise TdlibStoryPostUncertain(
        "Timed out waiting for TDLib story post confirmation",
        uncertain_reason="story_post_confirmation_timeout",
        verification_result={"temporary_story_id": str(temporary_story_id), "status": "posting"},
        result_payload=temporary_payload,
    )


def _get_saved_messages_chat_id(client: TdlibClient, config: Settings) -> int:
    me = _checked_send_query(client, {"@type": "getMe"}, config.tdlib_receive_timeout_seconds)
    user_id = me.get("id")
    if user_id is None:
        raise TdlibProfileQueryError(
            "TDLib getMe did not return user id", error_code="TDLIB_GET_ME_MISSING_ID"
        )
    chat = _checked_send_query(
        client,
        {"@type": "createPrivateChat", "user_id": int(user_id), "force": True},
        config.tdlib_auth_timeout_seconds,
    )
    chat_id = chat.get("id")
    if chat_id is None:
        raise TdlibProfileQueryError(
            "TDLib createPrivateChat did not return chat id",
            error_code="TDLIB_SAVED_MESSAGES_CHAT_MISSING_ID",
        )
    return int(chat_id)


def _ensure_can_post_story(client: TdlibClient, chat_id: int, config: Settings) -> None:
    response = _checked_send_query(
        client,
        {"@type": "canPostStory", "chat_id": chat_id},
        config.tdlib_auth_timeout_seconds,
    )
    response_type = response.get("@type")
    if response_type == "canPostStoryResultOk":
        return
    raise TdlibProfileQueryError(
        f"TDLib rejected story posting: {response_type or 'unknown'}",
        error_code=_can_post_story_error_code(response_type),
    )


def _story_privacy_settings(preset: str | None) -> dict[str, Any]:
    if preset in {None, "", "contacts"}:
        return {"@type": "storyPrivacySettingsContacts", "except_user_ids": []}
    if preset == "public":
        return {"@type": "storyPrivacySettingsEveryone", "except_user_ids": []}
    if preset == "close_friends":
        return {"@type": "storyPrivacySettingsCloseFriends"}
    raise TdlibProfileQueryError(
        f"Unsupported story privacy preset: {preset}",
        error_code="STORY_PRIVACY_PRESET_UNSUPPORTED",
    )


def _can_post_story_error_code(response_type: str | None) -> str:
    if not response_type:
        return "CAN_POST_STORY_UNKNOWN"
    code = response_type.removeprefix("canPostStoryResult")
    normalized = "".join(f"_{char}" if char.isupper() else char for char in code).strip("_").upper()
    return f"CAN_POST_STORY_{normalized or 'UNKNOWN'}"
