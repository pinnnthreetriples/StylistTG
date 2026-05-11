from app.models import AccountProfileAudioState, AccountStoryPost, JobState, StepStatus
from app.services.account_update_jobs import create_account_update_job
from app.services.account_update_plan import profile_payload_to_account_update_desired_state
from app.services.accounts import create_account
from app.services.story_drafts import create_story_draft, list_story_drafts
from app.workers.account_update_jobs import execute_account_update_job
from conftest import seed_audio_asset, seed_story_asset


def test_account_update_worker_executes_current_profile_steps(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    desired = profile_payload_to_account_update_desired_state(
        {
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": None,
        }
    )
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)

    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 0
    assert job.workflow_type == "account_update"
    assert job.job_state == JobState.COMPLETED
    assert [step.status for step in job.step_results] == [
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
        StepStatus.SUCCEEDED,
    ]


def test_account_update_worker_materializes_profile_audio_state(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    audio = seed_audio_asset(db_session)
    desired = {
        "profile": {
            "name": "Stylist TG",
            "bio": "Profile editor",
            "username": "stylist",
            "photo_asset_id": None,
        },
        "profile_audio": {"action": "add", "audio_asset_id": audio.id},
        "stories": [],
    }
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)

    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    audio_state = db_session.get(AccountProfileAudioState, account.id)
    assert exit_code == 0
    assert job.job_state == JobState.COMPLETED
    assert audio_state is not None
    assert audio_state.source_asset_id == audio.id
    assert audio_state.telegram_file_id == f"mock-file-{audio.id}"


def test_account_update_worker_materializes_story_post(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    story = seed_story_asset(db_session)
    desired = {
        "profile": {"name": "Stylist TG"},
        "profile_audio": {"action": "keep"},
        "stories": [
            {
                "action": "post_image",
                "asset_id": story.id,
                "caption": "New story",
                "privacy_preset": "contacts",
                "active_period_seconds": 86400,
            }
        ],
    }
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)

    exit_code = execute_account_update_job(job.id, session=db_session)

    story_post = db_session.query(AccountStoryPost).filter_by(account_id=account.id).one()
    assert exit_code == 0
    assert story_post.status == "posted"
    assert story_post.asset_id == story.id
    assert story_post.caption == "New story"


def test_account_update_worker_clears_applied_story_draft(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    story = seed_story_asset(db_session)
    draft = create_story_draft(
        db_session,
        {
            "account_id": account.id,
            "asset_id": story.id,
            "media_kind": "image",
            "caption": "New story",
            "privacy_preset": "contacts",
            "active_period_seconds": 86400,
            "protect_content": False,
        },
    )
    desired = {
        "profile": {"name": "Stylist TG"},
        "profile_audio": {"action": "keep"},
        "stories": [
            {
                "client_id": draft.id,
                "action": "post_image",
                "asset_id": story.id,
                "caption": "New story",
                "privacy_preset": "contacts",
                "active_period_seconds": 86400,
            }
        ],
    }
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)

    exit_code = execute_account_update_job(job.id, session=db_session)

    assert exit_code == 0
    assert list_story_drafts(db_session, account.id) == []
