from app.models import JobState, StepStatus
from app.services.step_policy import classify_account_update_job_outcome, is_hard_stop_error


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


def test_hard_stop_error_matching_normalizes_human_readable_runtime_errors() -> None:
    assert is_hard_stop_error("TDLib client closed unexpectedly")
    assert is_hard_stop_error("account lock corruption")
    assert is_hard_stop_error("missing-tdlib-credentials")
