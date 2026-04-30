import io
import json
import threading
from pathlib import Path

from rq.utils import import_attribute

from app.models import AccountStoryPost, AssetKind, JobState, StepStatus, TERMINAL_JOB_STATES
from app.services.accounts import create_account
from app.services.account_update_jobs import create_account_update_job
from app.services.jobs import create_profile_job, find_active_duplicate_job
from app.workers.account_update_jobs import execute_account_update_job
from app.workers import profile_jobs

from conftest import FakeExecutionUsableAdapter, seed_asset, seed_audio_asset, seed_story_asset


class FakeProcess:
    def __init__(self, stdout_lines: list[str], stderr: str = "", returncode: int = 0) -> None:
        self.stdout = io.StringIO("".join(stdout_lines))
        self.stderr = io.StringIO(stderr)
        self._returncode = returncode

    def wait(self, timeout=None):
        return self._returncode

    def communicate(self, timeout=None):
        return self.stdout.read(), self.stderr.read()

    def terminate(self):
        self._returncode = -15

    def kill(self):
        self._returncode = -9


def test_malformed_child_event_marks_job_failed(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(stdout_lines=["not-json\n"], returncode=0),
    )

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "malformed_child_event"


def test_child_stderr_summary_is_bounded_and_sanitized() -> None:
    summary = profile_jobs._stderr_summary(["line\n", "password=secret-token\n", "x" * 5000])

    assert summary is not None
    assert len(summary) <= 4096
    assert "password=secret-token" not in summary


def test_child_timeout_marks_job_failed(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    class TimeoutProcess(FakeProcess):
        def wait(self, timeout=None):
            raise profile_jobs.subprocess.TimeoutExpired(cmd="python", timeout=timeout)

    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: TimeoutProcess(
            stdout_lines=[
                json.dumps({"event": "runtime_started"}) + "\n",
                json.dumps({"event": "step_started", "step_key": "set_name", "step_type": "set_name"}) + "\n",
            ],
            returncode=0,
        ),
    )

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "child_process_timeout"
    assert job.step_results[0].status == StepStatus.UNCERTAIN
    assert job.step_results[0].uncertain_reason == "child_process_timeout"


def test_child_crash_after_step_started_marks_started_step_uncertain(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": "Profile editor", "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_lines=[
                json.dumps({"event": "runtime_started"}) + "\n",
                json.dumps({"event": "step_started", "step_key": "set_name", "step_type": "set_name"}) + "\n",
            ],
            returncode=1,
        ),
    )

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "profile_runtime_failed"
    assert job.step_results[0].status == StepStatus.UNCERTAIN
    assert job.step_results[0].uncertain_reason == "child_process_failed"


def test_child_timeout_applies_while_stdout_is_still_open(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    class HangingStdout:
        def __init__(self) -> None:
            self._first_read = True
            self._unblock = threading.Event()

        def __iter__(self):
            return self

        def __next__(self):
            if self._first_read:
                self._first_read = False
                return json.dumps({"event": "runtime_started"}) + "\n"
            self._unblock.wait()
            raise StopIteration

    class HangingProcess(FakeProcess):
        def __init__(self) -> None:
            super().__init__(stdout_lines=[], returncode=0)
            self.stdout = HangingStdout()

        def wait(self, timeout=None):
            raise profile_jobs.subprocess.TimeoutExpired(cmd="python", timeout=timeout)

    monkeypatch.setattr(profile_jobs.settings, "profile_job_timeout_seconds", 0.01)
    monkeypatch.setattr(profile_jobs.subprocess, "Popen", lambda *args, **kwargs: HangingProcess())

    result: dict[str, int] = {}
    finished = threading.Event()

    def run_worker() -> None:
        result["exit_code"] = profile_jobs.execute_profile_job(job.id, session=db_session)
        finished.set()

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    assert finished.wait(1.0)
    db_session.refresh(job)
    assert result["exit_code"] == 1
    assert job.job_state == JobState.FAILED
    assert job.failure_reason == "child_process_timeout"


def test_child_frozen_error_hard_stops_account(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )

    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess(
            stdout_lines=[
                json.dumps({"event": "runtime_started"}) + "\n",
                json.dumps(
                    {
                        "event": "runtime_failed",
                        "error_code": "FROZEN_METHOD_INVALID",
                        "error_class": "TdlibError",
                    }
                )
                + "\n",
            ],
            returncode=1,
        ),
    )

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    db_session.refresh(job)
    db_session.refresh(account)
    assert exit_code == 1
    assert job.job_state == JobState.MANUAL_INTERVENTION_NEEDED
    assert job.failure_reason == "tdlib_hard_stop:FROZEN_METHOD_INVALID"
    assert account.account_state == "manual_intervention_needed"
    assert account.runtime_state.recovery_marker == "tdlib_hard_stop:FROZEN_METHOD_INVALID"


def test_account_update_username_failure_after_success_is_partial(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    desired = {"profile": {"name": "Stylist TG", "username": "reserved"}}
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: _account_update_process_with_failed_step(args[0], "set_username"),
    )

    exit_code = execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert exit_code == 1
    assert job.job_state == JobState.PARTIALLY_COMPLETED
    assert _step_statuses(job) == {"set_name": StepStatus.SUCCEEDED, "set_username": StepStatus.FAILED}


def test_account_update_photo_failure_after_success_is_partial(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    photo = seed_asset(db_session)
    desired = {"profile": {"name": "Stylist TG", "photo_asset_id": photo.id}}
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: _account_update_process_with_failed_step(args[0], "set_profile_photo"),
    )

    execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert job.job_state == JobState.PARTIALLY_COMPLETED
    assert _step_statuses(job)["set_profile_photo"] == StepStatus.FAILED


def test_account_update_music_failure_after_profile_success_is_partial(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    audio = seed_audio_asset(db_session)
    desired = {
        "profile": {"name": "Stylist TG"},
        "profile_audio": {"action": "add", "audio_asset_id": audio.id},
    }
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: _account_update_process_with_failed_step(args[0], "upload_profile_audio"),
    )

    execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert job.job_state == JobState.PARTIALLY_COMPLETED
    assert _step_statuses(job)["upload_profile_audio"] == StepStatus.FAILED


def test_account_update_story_failure_after_profile_success_is_partial(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    story = seed_story_asset(db_session, kind=AssetKind.STORY_IMAGE)
    desired = {
        "profile": {"name": "Stylist TG"},
        "stories": [{"action": "post_image", "asset_id": story.id, "active_period_seconds": 86400}],
    }
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: _account_update_process_with_failed_step(args[0], "post_story_image"),
    )

    execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    assert job.job_state == JobState.PARTIALLY_COMPLETED
    assert _step_statuses(job)["post_story_image"] == StepStatus.FAILED


def test_account_update_hard_session_error_is_not_normal_partial(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    desired = {"profile": {"name": "Stylist TG", "username": "stylist"}}
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    monkeypatch.setattr(
        profile_jobs.subprocess,
        "Popen",
        lambda *args, **kwargs: _account_update_process_with_failed_step(
            args[0], "set_username", error_code="AUTH_KEY_UNREGISTERED"
        ),
    )

    execute_account_update_job(job.id, session=db_session)

    db_session.refresh(job)
    db_session.refresh(account)
    assert job.job_state == JobState.MANUAL_INTERVENTION_NEEDED
    assert job.failure_reason == "tdlib_hard_stop:AUTH_KEY_UNREGISTERED"
    assert account.account_state == "manual_intervention_needed"


def test_partially_completed_is_backend_terminal_and_does_not_dedup_block(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    desired = {"profile": {"name": "Stylist TG"}}
    first = create_account_update_job(db_session, account_id=account.id, desired_state=desired)
    first.job_state = JobState.PARTIALLY_COMPLETED
    db_session.commit()
    launched = False

    def fail_if_launched(*args, **kwargs):
        nonlocal launched
        launched = True
        return FakeProcess(stdout_lines=[], returncode=0)

    monkeypatch.setattr(profile_jobs.subprocess, "Popen", fail_if_launched)

    assert JobState.PARTIALLY_COMPLETED in TERMINAL_JOB_STATES
    assert execute_account_update_job(first.id, session=db_session) == 0
    assert launched is False
    assert find_active_duplicate_job(db_session, account.id, first.execution_intent_hash) is None


def test_terminal_profile_job_is_not_executed_again(db_session, monkeypatch) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = "execution_usable"
    db_session.commit()
    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
    )
    job.job_state = JobState.COMPLETED
    db_session.commit()
    launched = False

    def fail_if_launched(*args, **kwargs):
        nonlocal launched
        launched = True
        return FakeProcess(stdout_lines=[], returncode=0)

    monkeypatch.setattr(profile_jobs.subprocess, "Popen", fail_if_launched)

    exit_code = profile_jobs.execute_profile_job(job.id, session=db_session)

    assert exit_code == 0
    assert launched is False


def _account_update_process_with_failed_step(
    command: list[str], failed_step_type: str, *, error_code: str = "mock_step_failed"
) -> FakeProcess:
    plan_path = Path(command[command.index("--plan-file") + 1])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))["plan_json_snapshot"]
    lines = [json.dumps({"event": "runtime_started"}) + "\n"]
    for step in plan["steps"]:
        event = {"step_key": step["step_key"], "step_type": step["step_type"]}
        lines.append(json.dumps({"event": "step_started", **event}) + "\n")
        if step["step_type"] == failed_step_type:
            lines.append(
                json.dumps(
                    {
                        "event": "step_failed",
                        **event,
                        "error_code": error_code,
                        "error_class": "MockExecutionError",
                        "result_payload": {"mock": True},
                    }
                )
                + "\n"
            )
            lines.append(
                json.dumps(
                    {
                        "event": "runtime_failed",
                        "error_code": error_code,
                        "error_class": "MockExecutionError",
                    }
                )
                + "\n"
            )
            return FakeProcess(stdout_lines=lines, returncode=1)
        lines.append(
            json.dumps(
                {
                    "event": "step_succeeded",
                    **event,
                    "verification_attempted": False,
                    "verification_result": None,
                    "result_payload": {"mock": True, "applied": step["payload"]},
                }
            )
            + "\n"
        )
    return FakeProcess(stdout_lines=lines, returncode=0)


def _step_statuses(job) -> dict[str, str]:
    return {step.step_type: step.status for step in job.step_results}


def test_account_update_story_materialization_is_idempotent(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    story = seed_story_asset(db_session, kind=AssetKind.STORY_IMAGE)
    desired = {
        "profile": {"name": "Stylist TG"},
        "profile_audio": {"action": "keep"},
        "stories": [{"action": "post_image", "asset_id": story.id, "active_period_seconds": 86400}],
    }
    job = create_account_update_job(db_session, account_id=account.id, desired_state=desired)

    assert execute_account_update_job(job.id, session=db_session) == 0
    assert execute_account_update_job(job.id, session=db_session) == 0

    assert db_session.query(AccountStoryPost).filter_by(account_id=account.id).count() == 1


def test_rq_can_import_account_update_worker_function() -> None:
    func = import_attribute("app.workers.account_update_jobs.run_account_update_job")

    assert callable(func)
