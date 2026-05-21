"""Tests for attempt idempotency keys and transactional outbox.

Covers:
1. generate() determinism (random_id_hash stable per key)
2. reserve_in_redis duplicate returns False
3. lookup_attempt_id for existing key
4. Sender happy path: attempt.status=SENT, idempotency_key set, random_id passed
5. Sender TDLib non-flood error: attempt.status=SENDING (not FAILED), idem key preserved
6. Sender crash simulation: SENDING with external_message_id_provisional, unique constraint
7. Event outbox: is_published=False in same transaction as attempt.status=SENT
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from app.models import (
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroSafetyStatus,
    new_id,
)
from app.services.idempotency_keys import (
    IdempotencyConflict,
    IdempotencyKey,
    derive_random_id,
    generate,
    lookup_attempt_id,
    reserve_in_redis,
)
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.sender_service import (
    FakeTelegramCommentSender,
    SenderService,
    TelegramCommentSendError,
)
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account

_FROZEN_NOW = "2026-05-20T12:00:00+00:00"
_WS_ID = DEFAULT_LOCAL_WORKSPACE_ID
_TEST_CONFIG = SimpleNamespace(
    neuro_comment_tdlib_send_enabled=True,
    neuro_comment_require_redis_limiter_for_send=False,
)


@pytest.fixture(autouse=True)
def _allow_account_safety_gate(monkeypatch):
    def ok_gate(session, *, workspace_id: str, account_id: str, intent: str):
        _ = (session, workspace_id, account_id, intent)
        return SimpleNamespace(severity="ok", reasons=[])

    monkeypatch.setattr(
        "app.services.neuro_commenting.sender_service.evaluate_safety_gate",
        ok_gate,
    )


def _setup_attempt(db_session):
    """Create campaign + target + observed + approved comment + attempt."""
    account = seed_account(
        db_session,
        external_ref="+15550999001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=_WS_ID,
        actor_user_id="user-1",
        payload={"name": "Idem campaign", "dry_run": False, "send_mode": "manual_approval"},
    )
    campaign.status = "running"
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=_WS_ID,
        actor_user_id="user-1",
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=_WS_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@idem_test", "discussion_chat_id": "456"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="src-1",
        source_message_id="11",
        discussion_chat_id="456",
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
    db_session.add_all([observed, comment])
    db_session.flush()
    _approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=_WS_ID,
        actor_user_id="user-1",
    )
    db_session.commit()
    return attempt


# ---------------------------------------------------------------------------
# Unit tests: idempotency_keys module
# ---------------------------------------------------------------------------


class TestIdempotencyKeysGenerate:
    def test_generate_returns_idempotency_key(self) -> None:
        result = generate("attempt-123")
        assert isinstance(result, IdempotencyKey)
        assert len(result.key) == 36
        assert isinstance(result.random_id_hash, int)

    def test_random_id_hash_deterministic_from_key(self) -> None:
        result = generate("attempt-456")
        assert derive_random_id(result.key) == result.random_id_hash

    def test_random_id_hash_is_int64_range(self) -> None:
        result = generate("attempt-789")
        assert -(2**63) <= result.random_id_hash <= 2**63 - 1

    def test_different_attempts_get_different_keys(self) -> None:
        r1 = generate("attempt-1")
        r2 = generate("attempt-2")
        assert r1.key != r2.key


class TestReserveInRedis:
    def test_reserve_success(self) -> None:
        redis = MagicMock()
        redis.set.return_value = True
        result = reserve_in_redis(redis, key="test-key", attempt_id="att-1")
        assert result is True
        redis.set.assert_called_once_with("attempt:idem:test-key", "att-1", nx=True, ex=3600)

    def test_reserve_duplicate_returns_false(self) -> None:
        redis = MagicMock()
        redis.set.return_value = None
        result = reserve_in_redis(redis, key="test-key", attempt_id="att-1")
        assert result is False
        redis.set.assert_called_once()

    def test_reserve_custom_ttl(self) -> None:
        redis = MagicMock()
        redis.set.return_value = True
        reserve_in_redis(redis, key="k", attempt_id="a", ttl_seconds=7200)
        redis.set.assert_called_once_with("attempt:idem:k", "a", nx=True, ex=7200)


class TestLookupAttemptId:
    def test_lookup_existing_key(self) -> None:
        redis = MagicMock()
        redis.get.return_value = b"attempt-42"
        result = lookup_attempt_id(redis, key="some-key")
        assert result == "attempt-42"
        redis.get.assert_called_once_with("attempt:idem:some-key")

    def test_lookup_missing_key(self) -> None:
        redis = MagicMock()
        redis.get.return_value = None
        result = lookup_attempt_id(redis, key="missing")
        assert result is None
        redis.get.assert_called_once_with("attempt:idem:missing")

    def test_lookup_string_value(self) -> None:
        redis = MagicMock()
        redis.get.return_value = "attempt-str"
        result = lookup_attempt_id(redis, key="str-key")
        assert result == "attempt-str"
        redis.get.assert_called_once_with("attempt:idem:str-key")


# ---------------------------------------------------------------------------
# Integration tests: sender + idempotency
# ---------------------------------------------------------------------------


@freeze_time(_FROZEN_NOW)
def test_sender_happy_path_sets_idempotency_and_sends(db_session) -> None:
    attempt = _setup_attempt(db_session)
    fake_sender = FakeTelegramCommentSender(telegram_message_id="12345")
    redis_mock = MagicMock()
    redis_mock.set.return_value = True

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    result = service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    assert result.status == "sent"
    assert result.idempotency_key is not None
    assert len(result.idempotency_key) == 36
    assert result.telegram_message_id == "12345"
    assert result.external_message_id_provisional == 12345
    assert fake_sender.last_random_id is not None
    assert fake_sender.last_random_id == derive_random_id(result.idempotency_key)
    redis_mock.set.assert_called_once()


@freeze_time(_FROZEN_NOW)
def test_non_flood_error_leaves_sending_status(db_session) -> None:
    attempt = _setup_attempt(db_session)
    error = TelegramCommentSendError("TDLIB_UNKNOWN_ERROR", "connection reset")
    fake_sender = FakeTelegramCommentSender(error=error)
    redis_mock = MagicMock()
    redis_mock.set.return_value = True

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    result = service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    assert result.status == "sending"
    assert result.idempotency_key is not None
    assert result.error_code == "TDLIB_UNKNOWN_ERROR"
    redis_mock.set.assert_called_once()


@freeze_time(_FROZEN_NOW)
def test_redis_collision_raises_idempotency_conflict(db_session) -> None:
    attempt = _setup_attempt(db_session)
    fake_sender = FakeTelegramCommentSender(telegram_message_id="999")
    redis_mock = MagicMock()
    redis_mock.set.return_value = None  # NX fails

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    with pytest.raises(IdempotencyConflict):
        service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    assert attempt.status == "sending"
    assert attempt.idempotency_key is not None
    redis_mock.set.assert_called_once()


@freeze_time(_FROZEN_NOW)
def test_outbox_event_written_with_is_published_false(db_session) -> None:
    attempt = _setup_attempt(db_session)
    fake_sender = FakeTelegramCommentSender(telegram_message_id="777")
    redis_mock = MagicMock()
    redis_mock.set.return_value = True

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)
    db_session.flush()

    outbox_events = (
        db_session.query(NeuroCommentEvent)
        .filter(
            NeuroCommentEvent.attempt_id == attempt.id,
            NeuroCommentEvent.event_type == "comment_sent_provisional",
        )
        .all()
    )
    assert len(outbox_events) == 1
    event = outbox_events[0]
    assert event.is_published is False
    assert event.data_json["idempotency_key"] == attempt.idempotency_key
    redis_mock.set.assert_called_once()
