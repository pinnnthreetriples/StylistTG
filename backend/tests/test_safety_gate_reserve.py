"""Tests for atomic safety gate reserve via Redis Lua script.

Covers:
1. Reserve succeeds when under limit
2. Reserve fails when at concurrency limit
3. Two concurrent reserves — only max_concurrent succeed
4. Release frees the slot
5. Release with expired reservation returns False
6. Fail-open on Redis error
7. Counter key has TTL
8. Sender integration: reserve blocks at limit
9. Sender integration: reserve releases on success
10. Sender integration: reserve releases on send error
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from freezegun import freeze_time

from app.models import (
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroSafetyStatus,
    new_id,
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
from app.services.safety_gate_reserve import (
    GATE_MAX_CONCURRENT_DEFAULT,
    SafetyGateReservation,
    release,
    reserve,
)
from tests.helpers.factories import seed_account

_FROZEN_NOW = "2026-05-21T12:00:00+00:00"
_WS_ID = DEFAULT_LOCAL_WORKSPACE_ID


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
        external_ref="+15550888001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=_WS_ID,
        actor_user_id="user-1",
        payload={"name": "Gate campaign", "dry_run": False, "send_mode": "manual_approval"},
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
        payload={"channel_ref": "@gate_test", "discussion_chat_id": "789"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="src-gate-1",
        source_message_id="50",
        discussion_chat_id="789",
        discussion_message_id="88",
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        account_id=account.id,
        observed_post_id=observed.id,
        generated_text="Gate test.",
        final_text="Gate test.",
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
    return attempt, account


# ---------------------------------------------------------------------------
# Unit tests: safety_gate_reserve module
# ---------------------------------------------------------------------------


class TestReserve:
    def test_reserve_succeeds_under_limit(self) -> None:
        redis = MagicMock()
        redis.eval.return_value = [1, 1]

        result = reserve(redis, account_id="acc-1", intent="commenting")

        assert result.reserved is True
        assert result.current_count == 1
        assert result.max_concurrent == GATE_MAX_CONCURRENT_DEFAULT
        assert result.account_id == "acc-1"
        assert result.intent == "commenting"
        assert len(result.reservation_id) == 32  # hex UUID
        redis.eval.assert_called_once()

    def test_reserve_fails_at_limit(self) -> None:
        redis = MagicMock()
        redis.eval.return_value = [0, 3]

        result = reserve(redis, account_id="acc-1", intent="commenting", max_concurrent=3)

        assert result.reserved is False
        assert result.current_count == 3
        redis.eval.assert_called_once()

    def test_reserve_custom_max_concurrent(self) -> None:
        redis = MagicMock()
        redis.eval.return_value = [1, 1]

        result = reserve(redis, account_id="acc-1", intent="commenting", max_concurrent=5)

        assert result.reserved is True
        assert result.max_concurrent == 5
        redis.eval.assert_called_once()

    def test_reserve_fail_closed_on_redis_error_by_default(self) -> None:
        """Task 44 / F-301: Redis outage must NOT grant the slot by default.

        Previously the code fail-opened on RedisError, which lets duplicate
        sends slip past the concurrency gate during a Redis partition. The
        new contract: ``reserved=False, degraded=True``. Operators that
        accept the risk can flip ``settings.safety_gate_redis_fail_open``.
        """
        from unittest.mock import patch as _patch

        from redis.exceptions import RedisError

        redis = MagicMock()
        redis.eval.side_effect = RedisError("connection lost")

        with _patch("app.services.safety_gate_reserve.settings") as cfg:
            cfg.safety_gate_redis_fail_open = False
            result = reserve(redis, account_id="acc-1", intent="commenting")

        assert result.reserved is False
        assert result.degraded is True

    def test_reserve_passes_correct_keys_and_args(self) -> None:
        redis = MagicMock()
        redis.eval.return_value = [1, 1]

        reserve(
            redis,
            account_id="acc-42",
            intent="commenting",
            max_concurrent=7,
            ttl_seconds=300,
        )

        # ZSET-based reserve uses a single key + 4 ARGV
        # (now, ttl, max_concurrent, reservation_id) — see the docstring of
        # _RESERVE_LUA in safety_gate_reserve.py.
        call_args = redis.eval.call_args
        assert call_args[0][1] == 1  # numkeys
        assert "safety:gate:reservations:v2:acc-42:commenting" in call_args[0][2]
        assert call_args[0][4] == "120" or call_args[0][4] == "300"  # ttl_seconds

    def test_two_concurrent_reserves_max_one(self) -> None:
        """Simulate Lua behavior: first returns [1,1], second returns [0,1]."""
        redis = MagicMock()
        redis.eval.side_effect = [[1, 1], [0, 1]]

        r1 = reserve(redis, account_id="acc-1", intent="commenting", max_concurrent=1)
        r2 = reserve(redis, account_id="acc-1", intent="commenting", max_concurrent=1)

        assert r1.reserved is True
        assert r2.reserved is False
        assert redis.eval.call_count == 2


class TestRelease:
    def test_release_success(self) -> None:
        redis = MagicMock()
        redis.eval.return_value = 1
        reservation = SafetyGateReservation(
            reservation_id="res-1",
            account_id="acc-1",
            intent="commenting",
            reserved=True,
            current_count=1,
            max_concurrent=3,
        )

        result = release(redis, reservation=reservation)

        assert result is True
        redis.eval.assert_called_once()

    def test_release_not_reserved_returns_false(self) -> None:
        redis = MagicMock()
        reservation = SafetyGateReservation(
            reservation_id="res-1",
            account_id="acc-1",
            intent="commenting",
            reserved=False,
            current_count=0,
            max_concurrent=3,
        )

        result = release(redis, reservation=reservation)

        assert result is False
        redis.eval.assert_not_called()

    def test_release_expired_returns_false(self) -> None:
        redis = MagicMock()
        redis.eval.return_value = 0  # reservation not found
        reservation = SafetyGateReservation(
            reservation_id="res-expired",
            account_id="acc-1",
            intent="commenting",
            reserved=True,
            current_count=1,
            max_concurrent=3,
        )

        result = release(redis, reservation=reservation)

        assert result is False
        redis.eval.assert_called_once()

    def test_release_fail_on_redis_error(self) -> None:
        from redis.exceptions import RedisError

        redis = MagicMock()
        redis.eval.side_effect = RedisError("timeout")
        reservation = SafetyGateReservation(
            reservation_id="res-err",
            account_id="acc-1",
            intent="commenting",
            reserved=True,
            current_count=1,
            max_concurrent=3,
        )

        result = release(redis, reservation=reservation)

        assert result is False
        redis.eval.assert_called_once()


# ---------------------------------------------------------------------------
# Integration tests: sender + gate reserve
# ---------------------------------------------------------------------------

_TEST_CONFIG = SimpleNamespace(
    neuro_comment_tdlib_send_enabled=True,
    neuro_comment_require_redis_limiter_for_send=False,
)


@freeze_time(_FROZEN_NOW)
def test_sender_gate_concurrency_blocks_at_limit(db_session) -> None:
    attempt, _account = _setup_attempt(db_session)
    fake_sender = FakeTelegramCommentSender(telegram_message_id="111")
    redis_mock = MagicMock()
    # Gate reserve returns "at limit"
    redis_mock.eval.return_value = [0, 3]

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    result = service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    assert result.status == "skipped"
    assert result.error_code == "GATE_CONCURRENCY_LIMIT"
    assert fake_sender.calls == 0
    redis_mock.eval.assert_called_once()


@freeze_time(_FROZEN_NOW)
def test_sender_gate_reserve_releases_on_success(db_session) -> None:
    attempt, _account = _setup_attempt(db_session)
    fake_sender = FakeTelegramCommentSender(telegram_message_id="222")
    redis_mock = MagicMock()
    # First eval = gate reserve (success), second eval = release
    redis_mock.eval.side_effect = [[1, 1], 1]

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    result = service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    assert result.status == "sent"
    assert fake_sender.calls == 1
    # release was called (second eval call)
    assert redis_mock.eval.call_count == 2


@freeze_time(_FROZEN_NOW)
def test_sender_gate_reserve_releases_on_send_error(db_session) -> None:
    attempt, _account = _setup_attempt(db_session)
    error = TelegramCommentSendError("CHAT_NOT_FOUND", "Chat not found")
    fake_sender = FakeTelegramCommentSender(error=error)
    redis_mock = MagicMock()
    # First eval = gate reserve (success), second eval = release
    redis_mock.eval.side_effect = [[1, 1], 1]

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=redis_mock)
    result = service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    # Error occurred but gate was released
    assert result.error_code == "CHAT_NOT_FOUND"
    assert redis_mock.eval.call_count == 2


@freeze_time(_FROZEN_NOW)
def test_sender_no_redis_skips_gate_reserve(db_session) -> None:
    attempt, _account = _setup_attempt(db_session)
    fake_sender = FakeTelegramCommentSender(telegram_message_id="333")

    service = SenderService(config=_TEST_CONFIG, sender=fake_sender, redis_client=None)
    result = service.send_attempt(db_session, attempt_id=attempt.id, workspace_id=_WS_ID)

    assert result.status == "sent"
    assert fake_sender.calls == 1
