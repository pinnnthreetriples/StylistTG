import pytest
from freezegun import freeze_time

from app.models import (
    AccountProfileState,
    AccountState,
    AssetKind,
    AssetStatus,
    Job,
    JobState,
    JobStepResult,
    StepStatus,
    utc_now,
)
from app.config import Settings
from app.api.account_update import _account_update_error
from app.modules.account_editing.errors import (
    AccountAssetNotFoundError,
    AccountManualInterventionRequiredError,
    AccountNotFoundError,
    AccountRuntimeUnusableError,
    ProfileAudioUnsupportedFormatError,
    ProfileJobCooldownActiveError,
    StoriesDisabledError,
    StoriesTdlibLiveDisabledError,
)
from app.modules.account_editing import service as account_editing_service
from app.services.account_update_jobs import create_account_update_job
from app.services.accounts import create_account
from conftest import seed_asset, seed_audio_asset, seed_story_asset
from tests.helpers.factories import seed_operation_cooldown


COOLDOWN_ERROR_CLASS = "rate_" + "limit"


def test_account_update_preview_builds_unified_plan(app_client, db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.commit()

    response = app_client.post(
        "/api/account-update/preview",
        json={
            "account_id": account.id,
            "profile": {
                "name": "Stylist TG",
                "bio": "Profile editor",
                "username": "stylist",
                "photo_asset_id": None,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["workflow_type"] == "account_update"
    assert payload["can_create_job"] is True
    assert [step["step_type"] for step in payload["steps"]] == [
        "set_name",
        "set_bio",
        "set_username",
    ]


def test_account_update_create_queues_unified_job(app_client, db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.commit()
    enqueued: list[tuple[str, str]] = []

    def enqueue_workflow(*, workflow_type: str, job_id: str) -> bool:
        enqueued.append((workflow_type, job_id))
        return True

    monkeypatch.setattr(account_editing_service, "enqueue_workflow", enqueue_workflow)
    response = app_client.post(
        "/api/account-update/jobs",
        json={
            "account_id": account.id,
            "profile": {
                "name": "Stylist TG",
                "bio": "Profile editor",
                "username": "stylist",
                "photo_asset_id": None,
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_state"] == JobState.QUEUED
    assert payload["workflow_type"] == "account_update"
    assert enqueued == [("account_update", payload["job_id"])]


def test_account_update_create_does_not_depend_on_old_rq_enqueue(
    app_client, db_session, monkeypatch
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.commit()
    enqueued: list[str] = []

    def old_enqueue_should_not_run(job_id: str) -> bool:
        raise AssertionError("old rq enqueue path should not be called")

    monkeypatch.setattr(
        "app.job_queue.rq.enqueue_account_update_job",
        old_enqueue_should_not_run,
    )
    monkeypatch.setattr(
        account_editing_service,
        "enqueue_job",
        lambda job_id: enqueued.append(job_id) or True,
    )

    response = app_client.post(
        "/api/account-update/jobs",
        json={
            "account_id": account.id,
            "profile": {"name": "Stylist TG"},
        },
    )

    assert response.status_code == 201
    assert enqueued == [response.json()["job_id"]]


def test_account_update_create_returns_503_when_queue_enqueue_fails(
    app_client, db_session, monkeypatch
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.commit()

    monkeypatch.setattr(account_editing_service, "enqueue_job", lambda job_id: False)
    response = app_client.post(
        "/api/account-update/jobs",
        json={
            "account_id": account.id,
            "profile": {"name": "Stylist TG"},
        },
    )

    assert response.status_code == 503
    assert response.json()["error_code"] == "QUEUE_UNAVAILABLE"
    job = db_session.query(Job).one()
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "enqueue_failed"


def test_account_update_create_runs_inline_when_queue_fallback_is_enabled(
    app_client, db_session, monkeypatch
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.commit()
    inline_calls: list[str] = []

    def run_inline(job_id: str, *, session) -> None:
        inline_calls.append(job_id)
        job = session.get(Job, job_id)
        job.job_state = JobState.COMPLETED
        job.finished_at = utc_now()
        session.commit()

    monkeypatch.setattr(account_editing_service, "enqueue_job", lambda job_id: False)
    monkeypatch.setattr(account_editing_service, "execute_inline_fallback", run_inline)
    monkeypatch.setattr("app.api.account_update.settings.queue_inline_fallback_enabled", True)
    response = app_client.post(
        "/api/account-update/jobs",
        json={
            "account_id": account.id,
            "profile": {"name": "Stylist TG"},
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["job_state"] == JobState.COMPLETED
    assert inline_calls == [payload["job_id"]]


def _story_preview(app_client, account_id: str, story_id: str, **extra_story_fields):
    """Post a story preview request and return the response."""
    story_entry = {"action": "post_image", "asset_id": story_id, **extra_story_fields}
    return app_client.post(
        "/api/account-update/preview",
        json={
            "account_id": account_id,
            "profile": {"name": "Stylist TG"},
            "stories": [story_entry],
        },
    )


def _audio_preview(app_client, account_id: str, audio_id: str):
    """Post an audio preview request and return the response."""
    return app_client.post(
        "/api/account-update/preview",
        json={
            "account_id": account_id,
            "profile": {"name": "Stylist TG"},
            "profile_audio": {"action": "add", "audio_asset_id": audio_id},
        },
    )


def test_account_update_preview_accepts_profile_audio_asset(app_client, db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    audio = seed_audio_asset(db_session)
    db_session.commit()

    response = _audio_preview(app_client, account.id, audio.id)

    assert response.status_code == 200
    payload = response.json()
    assert [step["step_type"] for step in payload["steps"]][-2:] == [
        "upload_profile_audio",
        "add_profile_audio",
    ]
    assert payload["desired_state_normalized"]["profile_audio"]["audio_asset_id"] == audio.id


def test_account_update_preview_rejects_unsupported_profile_audio_asset(
    app_client, db_session
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    audio = seed_audio_asset(db_session)
    audio.mime = "audio/ogg"
    db_session.commit()

    response = _audio_preview(app_client, account.id, audio.id)

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "PROFILE_AUDIO_UNSUPPORTED_FORMAT"
    assert payload["field_errors"] == [
        {"field": "profile_audio", "message": "profile audio must be MP3 or M4A"}
    ]


@pytest.mark.parametrize(
    ("exc", "status_code", "error_code", "error_class"),
    [
        (AccountRuntimeUnusableError(), 400, "RUNTIME_UNUSABLE", "runtime"),
        (AccountNotFoundError(), 404, "ACCOUNT_NOT_FOUND", "not_found"),
        (
            AccountManualInterventionRequiredError(),
            400,
            "ACCOUNT_MANUAL_INTERVENTION_REQUIRED",
            "runtime",
        ),
        (
            ProfileJobCooldownActiveError(),
            400,
            "PROFILE_JOB_COOLDOWN_ACTIVE",
            COOLDOWN_ERROR_CLASS,
        ),
        (StoriesDisabledError(), 400, "STORIES_DISABLED", "capability"),
        (
            StoriesTdlibLiveDisabledError(),
            400,
            "STORIES_TDLIB_LIVE_DISABLED",
            "capability",
        ),
        (
            ProfileAudioUnsupportedFormatError(),
            400,
            "PROFILE_AUDIO_UNSUPPORTED_FORMAT",
            "validation",
        ),
    ],
)
def test_account_update_error_accepts_typed_account_editing_errors(
    exc, status_code, error_code, error_class
) -> None:
    app_error = _account_update_error(exc)

    assert app_error.status_code == status_code
    assert app_error.error_code == error_code
    assert app_error.error_class == error_class
    assert app_error.message == str(exc)


@pytest.mark.parametrize(
    ("exc", "status_code", "error_code", "error_class", "field_errors"),
    [
        (
            ValueError("account not found"),
            404,
            "ACCOUNT_NOT_FOUND",
            "not_found",
            [],
        ),
        (
            ValueError("asset kind is not profile_photo"),
            400,
            "VALIDATION_ERROR",
            "validation",
            [{"field": "photo_asset_id", "message": "asset kind is not profile_photo"}],
        ),
        (
            ValueError("asset is not ready for story execution"),
            400,
            "STORY_ASSET_NOT_READY",
            "validation",
            [{"field": "stories", "message": "asset is not ready for story execution"}],
        ),
        (
            ValueError("account requires manual intervention"),
            400,
            "ACCOUNT_MANUAL_INTERVENTION_REQUIRED",
            "runtime",
            [],
        ),
        (
            ValueError("profile job cooldown active"),
            400,
            "PROFILE_JOB_COOLDOWN_ACTIVE",
            COOLDOWN_ERROR_CLASS,
            [],
        ),
        (
            ValueError("stories live TDLib execution is not enabled"),
            400,
            "STORIES_TDLIB_LIVE_DISABLED",
            "capability",
            [],
        ),
    ],
)
def test_account_update_error_preserves_legacy_value_error_mapping(
    exc, status_code, error_code, error_class, field_errors
) -> None:
    app_error = _account_update_error(exc)

    assert app_error.status_code == status_code
    assert app_error.error_code == error_code
    assert app_error.error_class == error_class
    assert app_error.message == str(exc)
    assert app_error.field_errors == field_errors


def test_account_update_error_uses_typed_field_errors() -> None:
    app_error = _account_update_error(AccountAssetNotFoundError(field="stories"))

    assert app_error.status_code == 400
    assert app_error.error_code == "VALIDATION_ERROR"
    assert app_error.field_errors == [{"field": "stories", "message": "asset not found"}]


def test_account_update_preview_accepts_story_image_asset(app_client, db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    story = seed_story_asset(db_session)
    db_session.commit()

    response = _story_preview(
        app_client,
        account.id,
        story.id,
        caption="New story",
        privacy_preset="contacts",
        active_period_seconds=86400,
    )

    assert response.status_code == 200
    payload = response.json()
    assert [step["step_type"] for step in payload["steps"]][-3:] == [
        "validate_story_capabilities",
        "prepare_story_media",
        "post_story_image",
    ]


def test_account_update_preview_story_only_does_not_repeat_current_profile_photo(
    app_client, db_session
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    account.profile_state = AccountProfileState(
        account_id=account.id,
        first_name="Marina",
        last_name="Manina",
        bio="\u041c\u0430\u0440\u0438\u044f, \u043f\u0440\u043e\u0434\u0430\u0432\u0435\u0446 \u0438\u0438 \u0430\u0433\u0435\u043d\u0442\u043e\u0432",
        username="kkk4n44",
    )
    photo = seed_asset(db_session, asset_id="photo-current")
    story = seed_story_asset(db_session)
    previous_job = Job(
        account_id=account.id,
        job_state=JobState.COMPLETED,
        workflow_type="account_update",
        workflow_version=1,
        execution_intent_hash="previous-photo",
        job_payload_version=2,
        payload_json={"photo_asset_id": photo.id},
        desired_state_json=None,
        capability_snapshot_json={},
        plan_json_snapshot={
            "steps": [{"step_key": "set_profile_photo", "step_type": "set_profile_photo"}]
        },
        queued_at=utc_now(),
        started_at=utc_now(),
        finished_at=utc_now(),
    )
    db_session.add(previous_job)
    db_session.flush()
    db_session.add(
        JobStepResult(
            job_id=previous_job.id,
            step_key="set_profile_photo",
            step_type="set_profile_photo",
            status=StepStatus.SUCCEEDED,
            result_payload_json={"applied": {"photo_asset_id": photo.id}},
            started_at=utc_now(),
            finished_at=utc_now(),
        )
    )
    db_session.commit()

    response = app_client.post(
        "/api/account-update/preview",
        json={
            "account_id": account.id,
            "profile": {
                "name": "Marina Manina",
                "bio": "\u041c\u0430\u0440\u0438\u044f, \u043f\u0440\u043e\u0434\u0430\u0432\u0435\u0446 \u0438\u0438 \u0430\u0433\u0435\u043d\u0442\u043e\u0432",
                "username": "kkk4n44",
                "photo_asset_id": photo.id,
            },
            "stories": [{"action": "post_image", "asset_id": story.id}],
        },
    )

    assert response.status_code == 200
    assert [step["step_type"] for step in response.json()["steps"]] == [
        "validate_story_capabilities",
        "prepare_story_media",
        "post_story_image",
    ]


def test_account_update_preview_returns_story_asset_error_for_orphaned_story_asset(
    app_client, db_session
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    story = seed_story_asset(db_session)
    story.status = AssetStatus.ORPHANED
    db_session.commit()

    response = _story_preview(app_client, account.id, story.id)

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "STORY_ASSET_NOT_READY"
    assert payload["field_errors"] == [
        {"field": "stories", "message": "asset is not ready for story execution"}
    ]


def test_account_update_create_blocks_story_jobs_for_unvalidated_tdlib_live_path(
    db_session,
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    story = seed_story_asset(db_session)
    db_session.commit()
    config = Settings(
        profile_execution_adapter="tdlib",
        stories_tdlib_live_enabled=False,
        profile_job_cooldown_seconds=0,
    )

    try:
        create_account_update_job(
            db_session,
            account_id=account.id,
            desired_state={
                "profile": {"name": "Stylist TG"},
                "stories": [{"action": "post_image", "asset_id": story.id}],
            },
            config=config,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "stories live TDLib execution is not enabled"


@freeze_time("2026-01-15 12:00:00")
def test_account_update_create_blocks_operation_specific_safety_cooldown(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.runtime_health = "ready"
    seed_operation_cooldown(db_session, account_id=account.id)

    try:
        create_account_update_job(
            db_session,
            account_id=account.id,
            desired_state={"profile": {"username": "blocked_name"}},
            config=Settings(profile_job_cooldown_seconds=0),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "cooldown_active:username"


def test_account_update_preview_blocks_stories_when_disabled(
    app_client, db_session, monkeypatch
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    story = seed_story_asset(db_session)
    db_session.commit()
    monkeypatch.setattr("app.services.account_update_jobs.settings.stories_enabled", False)

    response = _story_preview(app_client, account.id, story.id)

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_create_job"] is False
    assert payload["blocking_errors"] == ["stories are disabled"]


@pytest.mark.parametrize(
    "media_kind,asset_kind",
    [("image", AssetKind.STORY_IMAGE), ("video", AssetKind.STORY_VIDEO)],
    ids=["image", "video"],
)
def test_account_update_create_allows_story_when_tdlib_live_enabled(
    db_session, media_kind, asset_kind
) -> None:
    account = create_account(db_session, external_ref="primary")
    account.account_state = AccountState.EXECUTION_USABLE
    story = seed_story_asset(db_session, kind=asset_kind)
    db_session.commit()
    config = Settings(
        profile_execution_adapter="tdlib",
        stories_tdlib_live_enabled=True,
        profile_job_cooldown_seconds=0,
    )

    job = create_account_update_job(
        db_session,
        account_id=account.id,
        desired_state={
            "profile": {"name": "Stylist TG"},
            "stories": [{"action": f"post_{media_kind}", "asset_id": story.id}],
        },
        config=config,
    )

    assert job.job_state == JobState.QUEUED
    assert [step["step_type"] for step in job.plan_json_snapshot["steps"]][-3:] == [
        "validate_story_capabilities",
        "prepare_story_media",
        f"post_story_{media_kind}",
    ]
