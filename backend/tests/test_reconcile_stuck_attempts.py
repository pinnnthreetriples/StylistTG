from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

from freezegun import freeze_time
from sqlalchemy.dialects import postgresql

from app.adapters.tdlib_auth import search_chat_messages
from app.config import Settings
from app.models import (
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroAttemptStatus,
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
    NeuroSafetyStatus,
    new_id,
)
from app.services.idempotency_keys import derive_random_id
from app.services.reconcile_stuck_attempts import run_reconcile_tick
from app.services.scheduler import (
    RECONCILE_STUCK_JOB_ID_PREFIX,
    RECONCILE_STUCK_TICK_SECONDS,
    enqueue_reconcile_stuck_tick,
    reconcile_stuck_tick,
    scheduler_report,
)
from tests.helpers.factories import seed_account

_FROZEN_NOW = "2026-05-22T12:00:00+00:00"
_FROZEN_DT = datetime(2026, 5, 22, 12, 0, 0, tzinfo=UTC)
_WORKSPACE_ID = DEFAULT_LOCAL_WORKSPACE_ID


class FakeSearchClient:
    def __init__(
        self,
        *,
        messages_by_random_id: dict[int, list[Any]] | None = None,
        error_account_ids: set[str] | None = None,
    ) -> None:
        self.messages_by_random_id = messages_by_random_id or {}
        self.error_account_ids = error_account_ids or set()
        self.calls: list[dict[str, object]] = []

    def search_chat_messages(
        self,
        *,
        account_id: str,
        chat_id: int,
        random_id: int | None = None,
        limit: int = 10,
    ) -> list[Any]:
        self.calls.append(
            {
                "account_id": account_id,
                "chat_id": chat_id,
                "random_id": random_id,
                "limit": limit,
            }
        )
        if account_id in self.error_account_ids:
            raise RuntimeError("temporary tdlib failure")
        return self.messages_by_random_id.get(int(random_id or 0), [])


def _seed_attempt(
    db_session,
    *,
    status: NeuroAttemptStatus = NeuroAttemptStatus.SENDING,
    updated_at: datetime | None = None,
    idempotency_key: str | None = None,
    discussion_chat_id: str | None = "456",
) -> NeuroCommentAttempt:
    account = seed_account(
        db_session,
        external_ref=f"+1555{new_id()[:8]}",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = NeuroCommentCampaign(
        id=new_id(),
        workspace_id=_WORKSPACE_ID,
        name=f"Reconcile campaign {new_id()}",
        status="running",
        dry_run=False,
    )
    target = NeuroCommentTarget(
        id=new_id(),
        campaign_id=campaign.id,
        channel_ref=f"@target_{new_id()[:8]}",
        discussion_chat_id=discussion_chat_id,
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="source-chat-1",
        source_message_id="source-message-1",
        discussion_chat_id=discussion_chat_id,
        discussion_message_id="99",
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        account_id=account.id,
        observed_post_id=observed.id,
        generated_text="Test.",
        final_text="Test.",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    attempt = NeuroCommentAttempt(
        id=new_id(),
        campaign_id=campaign.id,
        generated_comment_id=comment.id,
        account_id=account.id,
        target_id=target.id,
        observed_post_id=observed.id,
        status=status.value,
        idempotency_key=idempotency_key,
        external_message_id_provisional=123,
        updated_at=updated_at or (_FROZEN_DT - timedelta(minutes=10)),
    )
    db_session.add_all([campaign, target, observed, comment, attempt])
    db_session.commit()
    return attempt


@freeze_time(_FROZEN_NOW)
def test_reconcile_marks_found_stuck_attempt_sent(db_session) -> None:
    idempotency_key = str(uuid4())
    attempt = _seed_attempt(db_session, idempotency_key=idempotency_key)
    random_id = derive_random_id(idempotency_key)
    client = FakeSearchClient(
        messages_by_random_id={random_id: [SimpleNamespace(id=777, random_id=random_id)]}
    )

    report = run_reconcile_tick(db_session, client, now=_FROZEN_DT)
    db_session.commit()
    db_session.refresh(attempt)

    assert report.scanned == 1
    assert report.resolved_sent == 1
    assert attempt.status == NeuroAttemptStatus.SENT.value
    assert attempt.telegram_message_id == "777"
    assert attempt.external_message_id_provisional is None
    assert client.calls[0]["chat_id"] == 456
    assert client.calls[0]["random_id"] == random_id


@freeze_time(_FROZEN_NOW)
def test_reconcile_marks_missing_stuck_attempt_failed(db_session) -> None:
    attempt = _seed_attempt(db_session, idempotency_key=str(uuid4()))
    client = FakeSearchClient()

    report = run_reconcile_tick(db_session, client, now=_FROZEN_DT)
    db_session.commit()
    db_session.refresh(attempt)

    assert report.resolved_failed == 1
    assert attempt.status == NeuroAttemptStatus.FAILED.value
    assert attempt.error_code == "stuck_attempt_lost"
    assert attempt.external_message_id_provisional is None


@freeze_time(_FROZEN_NOW)
def test_reconcile_skips_stuck_attempt_without_idempotency_key(db_session) -> None:
    attempt = _seed_attempt(db_session, idempotency_key=None)
    client = FakeSearchClient()

    report = run_reconcile_tick(db_session, client, now=_FROZEN_DT)
    db_session.commit()
    db_session.refresh(attempt)

    assert report.scanned == 1
    assert report.skipped_no_idem_key == 1
    assert attempt.status == NeuroAttemptStatus.SENDING.value
    assert client.calls == []


@freeze_time(_FROZEN_NOW)
def test_reconcile_skips_recent_attempt(db_session) -> None:
    attempt = _seed_attempt(
        db_session,
        idempotency_key=str(uuid4()),
        updated_at=_FROZEN_DT - timedelta(minutes=2),
    )
    client = FakeSearchClient()

    report = run_reconcile_tick(db_session, client, now=_FROZEN_DT)
    db_session.commit()
    db_session.refresh(attempt)

    assert report.scanned == 0
    assert attempt.status == NeuroAttemptStatus.SENDING.value
    assert client.calls == []


@freeze_time(_FROZEN_NOW)
def test_reconcile_tdlib_error_keeps_attempt_sending(db_session) -> None:
    attempt = _seed_attempt(db_session, idempotency_key=str(uuid4()))
    assert attempt.account_id is not None
    client = FakeSearchClient(error_account_ids={attempt.account_id})

    report = run_reconcile_tick(db_session, client, now=_FROZEN_DT)
    db_session.commit()
    db_session.refresh(attempt)

    assert attempt.status == NeuroAttemptStatus.SENDING.value
    assert report.resolved_sent == 0
    assert report.resolved_failed == 0
    assert report.per_account_errors == {attempt.account_id: 1}


def test_reconcile_query_uses_for_update_skip_locked() -> None:
    class EmptyScalars:
        def all(self) -> list[object]:
            return []

    class EmptyResult:
        def scalars(self) -> EmptyScalars:
            return EmptyScalars()

    class RecordingSession:
        def __init__(self) -> None:
            self.statement: Any | None = None

        def execute(self, statement):
            self.statement = statement
            return EmptyResult()

    session = RecordingSession()

    run_reconcile_tick(session, FakeSearchClient(), now=_FROZEN_DT)  # type: ignore[arg-type]

    assert session.statement is not None
    compiled = str(session.statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in compiled
    assert "SKIP LOCKED" in compiled


def test_scheduler_report_registers_reconcile_stuck_tick() -> None:
    report = scheduler_report(Settings(_env_file=None))

    assert report.planned_ticks["reconcile_stuck_attempts"] == RECONCILE_STUCK_TICK_SECONDS


def test_enqueue_reconcile_stuck_tick_uses_scheduler_queue_and_two_minute_bucket(monkeypatch):
    class FakeQueue:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def enqueue_call(self, **kwargs) -> None:
            self.calls.append(kwargs)

    queue = FakeQueue()
    seen_queues: list[str] = []

    def fake_get_queue(name: str) -> FakeQueue:
        seen_queues.append(name)
        return queue

    monkeypatch.setattr("app.job_queue.rq.get_queue", fake_get_queue)

    assert enqueue_reconcile_stuck_tick(now=(RECONCILE_STUCK_TICK_SECONDS * 7) + 10) is True

    assert seen_queues == ["scheduler_jobs"]
    assert queue.calls == [
        {
            "func": reconcile_stuck_tick,
            "job_id": f"{RECONCILE_STUCK_JOB_ID_PREFIX}-7",
            "unique": True,
        }
    ]


def test_tdlib_search_chat_messages_filters_history_by_random_id() -> None:
    class RecordingClient:
        def __init__(self) -> None:
            self.queries: list[dict[str, object]] = []

        def send_query(self, payload: dict[str, object], timeout: float) -> dict[str, object]:
            self.queries.append(payload)
            return {
                "@type": "messages",
                "messages": [
                    {"id": 1, "random_id": 111},
                    {"id": 2, "random_id": 222},
                ],
            }

    client = RecordingClient()

    messages = search_chat_messages(
        client, chat_id=456, random_id=222, limit=1, timeout_seconds=0.1
    )

    assert messages == [{"id": 2, "random_id": 222}]
    assert client.queries == [
        {
            "@type": "getChatHistory",
            "chat_id": 456,
            "from_message_id": 0,
            "offset": 0,
            "limit": 50,
            "only_local": False,
        }
    ]
