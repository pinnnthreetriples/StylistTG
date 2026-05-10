import os

import pytest

from app.adapters.tdlib_auth import TdlibAuthAdapter, build_tdlib_auth_adapter
from app.adapters.tdlib_profile_execution import (
    TdlibProfileExecutionAdapter,
    classify_job_outcome,
    classify_step_outcome,
    map_step_to_tdlib_query,
    verify_username_result,
)
from app.config import Settings
from app.models import JobState, StepStatus


def test_map_step_to_tdlib_query_for_profile_operations() -> None:
    assert map_step_to_tdlib_query(
        {"step_type": "set_name", "payload": {"first_name": "Stylist", "last_name": "TG"}}
    )["@type"] == "setName"
    assert map_step_to_tdlib_query({"step_type": "set_bio", "payload": {"bio": "Hello"}})["@type"] == "setBio"
    assert map_step_to_tdlib_query(
        {"step_type": "set_username", "payload": {"username": "stylist"}}
    )["@type"] == "setUsername"


def test_map_profile_photo_step_uses_normalized_asset_path() -> None:
    query = map_step_to_tdlib_query(
        {
            "step_type": "set_profile_photo",
            "payload": {"asset_path": "C:/tmp/profile.jpg"},
        }
    )

    assert query["@type"] == "setProfilePhoto"
    assert query["photo"]["@type"] == "inputChatPhotoStatic"
    assert query["photo"]["photo"]["@type"] == "inputFileLocal"
    assert query["photo"]["photo"]["path"] == "C:/tmp/profile.jpg"


def test_map_profile_audio_add_uses_final_audio_file_id() -> None:
    query = map_step_to_tdlib_query(
        {
            "step_type": "add_profile_audio",
            "payload": {"telegram_file_id": "1242"},
        }
    )

    assert query == {"@type": "addProfileAudio", "file_id": 1242}


def test_username_verify_policy_marks_ambiguous_result_uncertain() -> None:
    verification = verify_username_result(
        desired_username="stylist",
        me_response={"usernames": {"editable_username": "other-user", "active_usernames": ["other-user"]}},
    )

    assert verification["status"] == StepStatus.UNCERTAIN
    assert verification["verification_attempted"] is True
    assert verification["uncertain_reason"] == "username_verify_mismatch"


def test_uncertain_classification_rules_match_frozen_v0_policy() -> None:
    assert classify_step_outcome("set_name", "uncertain") == StepStatus.UNCERTAIN
    assert classify_step_outcome("set_bio", "uncertain") == StepStatus.UNCERTAIN
    assert classify_step_outcome("set_profile_photo", "uncertain") == StepStatus.UNCERTAIN
    assert classify_step_outcome("set_username", "uncertain") == StepStatus.UNCERTAIN

    assert classify_job_outcome(
        [
            {"step_type": "set_name", "status": StepStatus.SUCCEEDED},
            {"step_type": "set_profile_photo", "status": StepStatus.UNCERTAIN},
        ]
    ) == JobState.PARTIALLY_COMPLETED
    assert classify_job_outcome(
        [
            {"step_type": "set_username", "status": StepStatus.UNCERTAIN},
        ]
    ) == JobState.MANUAL_INTERVENTION_NEEDED


class ErrorQueryClient:
    client_id = 1

    def __init__(self) -> None:
        self.closed = False

    def send(self, query: dict) -> None:
        pass

    def receive(self, timeout_seconds: float) -> dict | None:
        return {"@type": "authorizationStateReady"}

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        return {"@type": "error", "code": 420, "message": "FROZEN_METHOD_INVALID"}

    def close(self) -> None:
        self.closed = True


class ErrorQueryClientFactory:
    def __init__(self) -> None:
        self.client = ErrorQueryClient()

    def create(self, account_id: str) -> ErrorQueryClient:
        return self.client


class UsernamePurchaseErrorClient(ErrorQueryClient):
    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        return {"@type": "error", "code": 400, "message": "USERNAME_PURCHASE_AVAILABLE"}


class UsernamePurchaseErrorClientFactory:
    def __init__(self) -> None:
        self.client = UsernamePurchaseErrorClient()

    def create(self, account_id: str) -> UsernamePurchaseErrorClient:
        return self.client


class AudioUploadIncompleteClient(ErrorQueryClient):
    def __init__(self) -> None:
        super().__init__()
        self.queries: list[dict] = []

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        self.queries.append(query)
        if query["@type"] == "preliminaryUploadFile":
            return {
                "@type": "file",
                "id": 1238,
                "remote": {
                    "@type": "remoteFile",
                    "is_uploading_active": True,
                    "is_uploading_completed": False,
                },
            }
        return {"@type": "ok"}


class AudioUploadCompletesByUpdateClient(AudioUploadIncompleteClient):
    def __init__(self) -> None:
        super().__init__()
        self.ready_emitted = False
        self.upload_update_emitted = False

    def receive(self, timeout_seconds: float) -> dict | None:
        if not self.ready_emitted:
            self.ready_emitted = True
            return {"@type": "authorizationStateReady"}
        if not self.upload_update_emitted:
            self.upload_update_emitted = True
            return {
                "@type": "updateFile",
                "file": {
                    "@type": "file",
                    "id": 1238,
                    "remote": {
                        "@type": "remoteFile",
                        "is_uploading_active": False,
                        "is_uploading_completed": True,
                    },
                },
            }
        return None


class AudioUploadSettlesByUpdateClient(AudioUploadIncompleteClient):
    def __init__(self) -> None:
        super().__init__()
        self.ready_emitted = False
        self.upload_update_emitted = False

    def receive(self, timeout_seconds: float) -> dict | None:
        if not self.ready_emitted:
            self.ready_emitted = True
            return {"@type": "authorizationStateReady"}
        if not self.upload_update_emitted:
            self.upload_update_emitted = True
            return {
                "@type": "updateFile",
                "file": {
                    "@type": "file",
                    "id": 1238,
                    "size": 4096,
                    "expected_size": 4096,
                    "remote": {
                        "@type": "remoteFile",
                        "is_uploading_active": False,
                        "is_uploading_completed": False,
                        "uploaded_size": 4096,
                    },
                },
            }
        return None


class AudioUploadIncompleteClientFactory:
    def __init__(self, client: AudioUploadIncompleteClient | None = None) -> None:
        self.client = client or AudioUploadIncompleteClient()

    def create(self, account_id: str) -> AudioUploadIncompleteClient:
        return self.client


class SavedMessageAudioClient(ErrorQueryClient):
    def __init__(self, *, send_succeeds: bool = True) -> None:
        super().__init__()
        self.queries: list[dict] = []
        self.ready_emitted = False
        self.updates: list[dict] = []
        self.send_succeeds = send_succeeds

    def receive(self, timeout_seconds: float) -> dict | None:
        if not self.ready_emitted:
            self.ready_emitted = True
            return {"@type": "authorizationStateReady"}
        if self.updates:
            return self.updates.pop(0)
        return None

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        self.queries.append(query)
        query_type = query["@type"]
        if query_type == "getMe":
            return {"@type": "user", "id": 12345}
        if query_type == "createPrivateChat":
            return {"@type": "chat", "id": 12345}
        if query_type == "sendMessage":
            old_message_id = 1
            if self.send_succeeds:
                self.updates.append(
                    {
                        "@type": "updateMessageSendSucceeded",
                        "old_message_id": old_message_id,
                        "message": {
                            "@type": "message",
                            "id": 94371840,
                            "content": {
                                "@type": "messageAudio",
                                "audio": {
                                    "@type": "audio",
                                    "audio": {
                                        "@type": "file",
                                        "id": 1242,
                                        "remote": {
                                            "@type": "remoteFile",
                                            "is_uploading_active": False,
                                            "is_uploading_completed": True,
                                        },
                                    },
                                },
                            },
                        },
                    }
                )
            return {
                "@type": "message",
                "id": old_message_id,
                "content": {
                    "@type": "messageAudio",
                    "audio": {"@type": "audio", "audio": {"@type": "file", "id": 1238}},
                },
            }
        if query_type == "addProfileAudio":
            return {"@type": "ok"}
        if query_type == "deleteMessages":
            return {"@type": "ok"}
        return {"@type": "ok"}


class SavedMessageAudioClientFactory:
    def __init__(self, client: SavedMessageAudioClient) -> None:
        self.client = client

    def create(self, account_id: str) -> SavedMessageAudioClient:
        return self.client


class StoryPostClient:
    client_id = 2

    def __init__(self, *, can_post_response: dict | None = None, story_post_succeeds: bool = True) -> None:
        self.closed = False
        self.queries: list[dict] = []
        self.can_post_response = can_post_response or {"@type": "canPostStoryResultOk"}
        self.story_post_succeeds = story_post_succeeds
        self.ready_emitted = False
        self.updates: list[dict] = []

    def send(self, query: dict) -> None:
        pass

    def receive(self, timeout_seconds: float) -> dict | None:
        if not self.ready_emitted:
            self.ready_emitted = True
            return {"@type": "authorizationStateReady"}
        if self.updates:
            return self.updates.pop(0)
        return None

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        self.queries.append(query)
        query_type = query["@type"]
        if query_type == "getMe":
            return {"@type": "user", "id": 12345}
        if query_type == "createPrivateChat":
            return {"@type": "chat", "id": 777000}
        if query_type == "canPostStory":
            return self.can_post_response
        if query_type == "postStory":
            if self.story_post_succeeds:
                self.updates.append(
                    {
                        "@type": "updateStoryPostSucceeded",
                        "old_story_id": 42,
                        "story": {"@type": "story", "id": 99, "poster_chat_id": query["chat_id"]},
                    }
                )
            return {"@type": "story", "id": 42, "poster_chat_id": query["chat_id"]}
        return {}

    def close(self) -> None:
        self.closed = True


class StoryPostClientFactory:
    def __init__(self, client: StoryPostClient) -> None:
        self.client = client

    def create(self, account_id: str) -> StoryPostClient:
        return self.client


def test_profile_adapter_posts_photo_story_with_tdlib_contract(tmp_path) -> None:
    client = StoryPostClient()
    adapter = TdlibProfileExecutionAdapter(
        client_factory=StoryPostClientFactory(client),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
            profile_audio_upload_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "story_1_post",
                        "step_type": "post_story_image",
                        "payload": {
                            "client_id": "draft-1",
                            "asset_id": "asset-1",
                            "asset_path": "C:/tmp/story.jpg",
                            "media_kind": "image",
                            "caption": "Привет",
                            "privacy_preset": "contacts",
                            "active_period_seconds": 86400,
                            "protect_content": True,
                        },
                    }
                ]
            },
            {},
        )
    )

    post_query = next(query for query in client.queries if query["@type"] == "postStory")
    assert post_query == {
        "@type": "postStory",
        "chat_id": 777000,
        "content": {
            "@type": "inputStoryContentPhoto",
            "photo": {"@type": "inputFileLocal", "path": "C:/tmp/story.jpg"},
            "added_sticker_file_ids": [],
        },
        "areas": {"@type": "inputStoryAreas", "areas": []},
        "caption": {"@type": "formattedText", "text": "Привет", "entities": []},
        "privacy_settings": {"@type": "storyPrivacySettingsContacts", "except_user_ids": []},
        "album_ids": [],
        "active_period": 86400,
        "from_story_full_id": None,
        "is_posted_to_chat_page": False,
        "protect_content": True,
    }
    assert events[-2]["event"] == "step_succeeded"
    assert events[-2]["result_payload"]["story_post"] == {
        "asset_id": "asset-1",
        "media_kind": "image",
        "caption": "Привет",
        "privacy_preset": "contacts",
        "active_period_seconds": 86400,
        "protect_content": True,
        "telegram_story_id": "99",
        "temporary_story_id": "42",
        "status": "posted",
        "raw_tdlib_json": {"@type": "story", "id": 99, "poster_chat_id": 777000},
    }
    assert events[-1]["event"] == "runtime_closed"


def test_profile_adapter_blocks_photo_story_when_tdlib_can_post_story_rejects(tmp_path) -> None:
    client = StoryPostClient(can_post_response={"@type": "canPostStoryResultPremiumNeeded"})
    adapter = TdlibProfileExecutionAdapter(
        client_factory=StoryPostClientFactory(client),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
            profile_audio_upload_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "story_1_post",
                        "step_type": "post_story_image",
                        "payload": {
                            "asset_id": "asset-1",
                            "asset_path": "C:/tmp/story.jpg",
                            "caption": "",
                            "privacy_preset": "contacts",
                            "active_period_seconds": 86400,
                            "protect_content": False,
                        },
                    }
                ]
            },
            {},
        )
    )

    assert events[-2]["event"] == "step_failed"
    assert events[-2]["error_code"] == "CAN_POST_STORY_PREMIUM_NEEDED"
    assert all(query["@type"] != "postStory" for query in client.queries)


def test_profile_adapter_posts_video_story_with_tdlib_contract(tmp_path) -> None:
    client = StoryPostClient()
    adapter = TdlibProfileExecutionAdapter(
        client_factory=StoryPostClientFactory(client),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "story_1_post",
                        "step_type": "post_story_video",
                        "payload": {
                            "client_id": "draft-1",
                            "asset_id": "asset-1",
                            "asset_path": "C:/tmp/story.mp4",
                            "media_kind": "video",
                            "caption": "Видео",
                            "privacy_preset": "public",
                            "active_period_seconds": 86400,
                            "protect_content": False,
                        },
                    }
                ]
            },
            {},
        )
    )

    post_query = next(query for query in client.queries if query["@type"] == "postStory")
    assert post_query == {
        "@type": "postStory",
        "chat_id": 777000,
        "content": {
            "@type": "inputStoryContentVideo",
            "video": {"@type": "inputFileLocal", "path": "C:/tmp/story.mp4"},
            "added_sticker_file_ids": [],
            "duration": 0,
            "cover_frame_timestamp": 0,
            "is_animation": False,
        },
        "areas": {"@type": "inputStoryAreas", "areas": []},
        "caption": {"@type": "formattedText", "text": "Видео", "entities": []},
        "privacy_settings": {"@type": "storyPrivacySettingsEveryone", "except_user_ids": []},
        "album_ids": [],
        "active_period": 86400,
        "from_story_full_id": None,
        "is_posted_to_chat_page": False,
        "protect_content": False,
    }
    assert events[-2]["event"] == "step_succeeded"
    assert events[-2]["result_payload"]["story_post"] == {
        "asset_id": "asset-1",
        "media_kind": "video",
        "caption": "Видео",
        "privacy_preset": "public",
        "active_period_seconds": 86400,
        "protect_content": False,
        "telegram_story_id": "99",
        "temporary_story_id": "42",
        "status": "posted",
        "raw_tdlib_json": {"@type": "story", "id": 99, "poster_chat_id": 777000},
    }
    assert events[-1]["event"] == "runtime_closed"


def test_profile_adapter_marks_story_uncertain_without_tdlib_success_update(tmp_path) -> None:
    client = StoryPostClient(story_post_succeeds=False)
    adapter = TdlibProfileExecutionAdapter(
        client_factory=StoryPostClientFactory(client),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.02,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "story_1_post",
                        "step_type": "post_story_image",
                        "payload": {
                            "asset_id": "asset-1",
                            "asset_path": "C:/tmp/story.jpg",
                            "caption": "",
                            "privacy_preset": "contacts",
                            "active_period_seconds": 86400,
                            "protect_content": False,
                        },
                    }
                ]
            },
            {},
        )
    )

    assert events[-2]["event"] == "step_uncertain"
    assert events[-2]["uncertain_reason"] == "story_post_confirmation_timeout"
    assert events[-2]["result_payload"]["story_post"]["temporary_story_id"] == "42"
    assert events[-1]["event"] == "runtime_closed"


def test_profile_adapter_emits_hard_stop_error_code_for_frozen_tdlib_error(tmp_path) -> None:
    adapter = TdlibProfileExecutionAdapter(
        client_factory=ErrorQueryClientFactory(),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {"steps": [{"step_key": "set_name:0", "step_type": "set_name", "payload": {"name": "A"}}]},
            {},
        )
    )

    assert events[-2]["event"] == "step_failed"
    assert events[-2]["error_code"] == "FROZEN_METHOD_INVALID"
    assert events[-1]["event"] == "runtime_failed"
    assert events[-1]["error_code"] == "FROZEN_METHOD_INVALID"


def test_profile_adapter_preserves_username_purchase_error_code(tmp_path) -> None:
    adapter = TdlibProfileExecutionAdapter(
        client_factory=UsernamePurchaseErrorClientFactory(),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "set_username",
                        "step_type": "set_username",
                        "payload": {"username": "premium_name"},
                    }
                ]
            },
            {},
        )
    )

    assert events[-2]["event"] == "step_failed"
    assert events[-2]["error_code"] == "USERNAME_PURCHASE_AVAILABLE"
    assert events[-1]["event"] == "runtime_failed"
    assert events[-1]["error_code"] == "USERNAME_PURCHASE_AVAILABLE"


def test_profile_adapter_sends_profile_audio_to_saved_messages_before_add(tmp_path) -> None:
    client = SavedMessageAudioClient()
    factory = SavedMessageAudioClientFactory(client)
    adapter = TdlibProfileExecutionAdapter(
        client_factory=factory,
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
            profile_audio_upload_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "upload_profile_audio",
                        "step_type": "upload_profile_audio",
                        "payload": {
                            "audio_asset_id": "audio-1",
                            "asset_path": "C:/tmp/profile.mp3",
                            "title": "Track title",
                        },
                    },
                    {
                        "step_key": "add_profile_audio",
                        "step_type": "add_profile_audio",
                        "payload": {"audio_asset_id": "audio-1"},
                    },
                ]
            },
            {},
        )
    )

    assert [event["event"] for event in events].count("step_succeeded") == 2
    assert [query["@type"] for query in client.queries] == [
        "getMe",
        "createPrivateChat",
        "sendMessage",
        "addProfileAudio",
        "deleteMessages",
    ]
    assert client.queries[2]["input_message_content"]["@type"] == "inputMessageAudio"
    assert client.queries[2]["input_message_content"]["title"] == "Track title"
    assert client.queries[3] == {"@type": "addProfileAudio", "file_id": 1242}


def test_profile_adapter_fails_when_saved_audio_message_is_not_confirmed(tmp_path) -> None:
    client = SavedMessageAudioClient(send_succeeds=False)
    factory = SavedMessageAudioClientFactory(client)
    adapter = TdlibProfileExecutionAdapter(
        client_factory=factory,
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.01,
            profile_audio_upload_timeout_seconds=0.01,
        ),
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "upload_profile_audio",
                        "step_type": "upload_profile_audio",
                        "payload": {
                            "audio_asset_id": "audio-1",
                            "asset_path": "C:/tmp/profile.mp3",
                        },
                    },
                    {
                        "step_key": "add_profile_audio",
                        "step_type": "add_profile_audio",
                        "payload": {"audio_asset_id": "audio-1"},
                    },
                ]
            },
            {},
        )
    )

    assert events[-2]["event"] == "step_failed"
    assert events[-2]["error_code"] == "PROFILE_AUDIO_MESSAGE_SEND_TIMEOUT"
    assert events[-1]["event"] == "runtime_failed"
    assert [query["@type"] for query in client.queries] == ["getMe", "createPrivateChat", "sendMessage"]


def test_profile_adapter_inspect_runtime_times_out_when_tdlib_is_silent(tmp_path) -> None:
    class SilentClient:
        client_id = 0

        def send(self, query):
            pass

        def receive(self, timeout_seconds):
            return None

        def send_query(self, query, timeout_seconds):
            return {}

        def close(self):
            pass

    class SilentFactory:
        def create(self, account_id):
            return SilentClient()

    adapter = TdlibProfileExecutionAdapter(
        client_factory=SilentFactory(),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.02,
        ),
    )

    result = adapter.inspect_runtime("account-1")

    assert result["ok"] is False
    assert result["runtime_health"] == "timeout"


def test_profile_adapter_create_failure_yields_runtime_failed(tmp_path) -> None:
    class RaisingFactory:
        def create(self, account_id):
            raise OSError("tdjson unavailable")

    adapter = TdlibProfileExecutionAdapter(
        client_factory=RaisingFactory(),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_receive_timeout_seconds=0.01,
            tdlib_auth_timeout_seconds=0.02,
        ),
    )

    events = list(adapter.execute("account-1", {"steps": []}, {}))

    assert events == [
        {
            "event": "runtime_failed",
            "error_code": "tdlib_runtime_failed",
            "error_class": "OSError",
            "error": "tdjson unavailable",
        }
    ]


@pytest.mark.integration
@pytest.mark.live
def test_real_tdlib_adapter_can_be_constructed_when_credentials_exist() -> None:
    if not os.getenv("TDLIB_API_ID") or not os.getenv("TDLIB_API_HASH"):
        pytest.skip("Set TDLIB_API_ID and TDLIB_API_HASH to run real TDLib integration tests")

    adapter = build_tdlib_auth_adapter()

    assert isinstance(adapter, TdlibAuthAdapter)
    assert adapter._config.tdlib_api_id is not None
    assert adapter._config.tdlib_api_hash is not None
