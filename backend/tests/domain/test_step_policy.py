from app.models import JobState, StepStatus
from app.services.step_policy import classify_account_update_job_outcome, is_hard_stop_error


def test_unknown_failure_after_success_is_failed_not_partial() -> None:
    outcome = classify_account_update_job_outcome(
        [
            {"step_key": "set_name", "step_type": "set_name", "status": StepStatus.SUCCEEDED},
            {"step_key": "billing_sync", "step_type": "billing_sync", "status": StepStatus.FAILED},
        ]
    )

    assert outcome == JobState.FAILED


def test_dynamic_story_step_failure_after_success_is_partial() -> None:
    outcome = classify_account_update_job_outcome(
        [
            {"step_key": "set_name", "step_type": "set_name", "status": StepStatus.SUCCEEDED},
            {"step_key": "story_1_post", "step_type": "story_1_post", "status": StepStatus.FAILED},
        ]
    )

    assert outcome == JobState.PARTIALLY_COMPLETED


def test_story_step_key_failure_after_success_is_partial_when_type_is_generic() -> None:
    outcome = classify_account_update_job_outcome(
        [
            {"step_key": "set_name", "step_type": "set_name", "status": StepStatus.SUCCEEDED},
            {
                "step_key": "story_1_post",
                "step_type": "post_story_image",
                "status": StepStatus.FAILED,
            },
        ]
    )

    assert outcome == JobState.PARTIALLY_COMPLETED


def test_uncertain_steps_require_a_meaningful_success_for_partial() -> None:
    assert (
        classify_account_update_job_outcome(
            [{"step_key": "set_name", "step_type": "set_name", "status": StepStatus.UNCERTAIN}]
        )
        == JobState.FAILED
    )
    assert (
        classify_account_update_job_outcome(
            [
                {"step_key": "set_name", "step_type": "set_name", "status": StepStatus.SUCCEEDED},
                {"step_key": "set_bio", "step_type": "set_bio", "status": StepStatus.UNCERTAIN},
            ]
        )
        == JobState.PARTIALLY_COMPLETED
    )


def test_hard_stop_error_overrides_other_step_outcomes() -> None:
    outcome = classify_account_update_job_outcome(
        [
            {"step_key": "set_name", "step_type": "set_name", "status": StepStatus.SUCCEEDED},
        ],
        hard_stop_error_code="session revoked",
    )

    assert outcome == JobState.MANUAL_INTERVENTION_NEEDED


def test_hard_stop_error_matching_normalizes_human_readable_runtime_errors() -> None:
    assert is_hard_stop_error("TDLib client closed unexpectedly")
    assert is_hard_stop_error("account lock corruption")
    assert is_hard_stop_error("missing-tdlib-credentials")


def test_hard_stop_error_ignores_empty_and_unrelated_errors() -> None:
    assert not is_hard_stop_error(None)
    assert not is_hard_stop_error("")
    assert not is_hard_stop_error("profile update failed")
