from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings, settings
from app.services.neuro_commenting import rate_limiter
from app.models import (
    Account,
    AccountBehaviorProfile,
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountState,
    NeuroCommentCampaignAccount,
    NeuroAttemptStatus,
    NeuroCommentAttempt,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroSafetyStatus,
    new_id,
)
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.errors import NeuroConflictError, NeuroRuntimeDisabledError
from app.services.neuro_commenting.sender_service import (
    FakeTelegramCommentSender,
    SenderService,
    TelegramCommentSendError,
    build_telegram_comment_sender,
)
from app.services.neuro_commenting.tdlib_comment_sender import TdlibTelegramCommentSender
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account
from tests.test_neuro_commenting_rate_limiter import FakeRedis


@pytest.fixture(autouse=True)
def _allow_account_safety_gate(monkeypatch):
    def ok_gate(session, *, workspace_id: str, account_id: str, intent: str):
        _ = (session, workspace_id, account_id, intent)
        return SimpleNamespace(severity="ok", reasons=[])

    monkeypatch.setattr(
        "app.services.neuro_commenting.sender_service.evaluate_safety_gate",
        ok_gate,
    )


class DenyExceededLimiter:
    def __init__(self) -> None:
        self.called = False

    def reserve(self, scope):
        _ = scope
        self.called = True
        return SimpleNamespace(
            allowed=False,
            reservation_id=None,
            reason="account comments_per_hour limit exceeded",
            retry_after_seconds=60,
            checked_limits=[],
        )

    def commit(self, reservation):  # pragma: no cover - denied reservations are not committed
        _ = reservation
        raise AssertionError("commit should not be called for denied reservation")

    def rollback(self, reservation):  # pragma: no cover - denied reservations are not rolled back
        _ = reservation
        raise AssertionError("rollback should not be called for denied reservation")


class _RecordingBehaviorHook:
    def __init__(self, order: list[str] | None = None) -> None:
        self.order = order
        self.calls = []

    def before_send(self, **kwargs) -> None:
        if self.order is not None:
            self.order.append("behavior")
        self.calls.append(kwargs)


class _OrderingSender(FakeTelegramCommentSender):
    def __init__(self, order: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._order = order

    def send_comment(self, **kwargs):
        self._order.append("send")
        return super().send_comment(**kwargs)


def _approved_comment_with_attempt(db_session):
    account = seed_account(
        db_session,
        external_ref="+15550105001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Sender campaign", "dry_run": False, "send_mode": "manual_approval"},
    )
    campaign.status = "running"
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@example", "discussion_chat_id": "456"},
    )
    observed = NeuroCommentObservedPost(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        source_chat_id="source-chat-1",
        source_message_id="42",
        discussion_chat_id="456",
        discussion_message_id="99",
    )
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        target_id=target.id,
        account_id=account.id,
        observed_post_id=observed.id,
        generated_text="Интересно.",
        final_text="Интересно.",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    db_session.add_all([observed, comment])
    db_session.flush()
    approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()
    return campaign, target, approved, attempt


def test_approve_comment_is_idempotent(db_session) -> None:
    _campaign, _target, comment, first_attempt = _approved_comment_with_attempt(db_session)

    _comment, second_attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()

    assert second_attempt.id == first_attempt.id
    assert (
        db_session.query(NeuroCommentAttempt).filter_by(generated_comment_id=comment.id).count()
        == 1
    )


def test_manual_send_fails_closed_when_disabled(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)

    with pytest.raises(NeuroRuntimeDisabledError) as exc_info:
        SenderService(config=settings).send_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    assert exc_info.value.error_code == "NEURO_COMMENT_SEND_DISABLED"


def test_behavior_emulator_live_send_flag_defaults_disabled() -> None:
    assert settings.behavior_emulator_live_send_enabled is False


def test_behavior_emulator_live_send_flag_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("BEHAVIOR_EMULATOR_LIVE_SEND_ENABLED", "true")

    assert Settings().behavior_emulator_live_send_enabled is True


def test_default_sender_uses_settings_redis_limiter_when_required(db_session, monkeypatch) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    redis = FakeRedis()
    monkeypatch.setattr(rate_limiter, "redis_from_url", lambda: redis)
    config = SimpleNamespace(
        neuro_comment_tdlib_send_enabled=True,
        neuro_comment_require_redis_limiter_for_send=True,
    )
    sender = FakeTelegramCommentSender(telegram_message_id="telegram-default-limiter")

    sent = SenderService(config=config, sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert sent.status == NeuroAttemptStatus.SENT.value
    assert sender.calls == 1
    assert any(":reservation:" in key for key in redis.deleted)


def test_preflight_blocks_blacklisted_target_before_enqueue(db_session) -> None:
    _campaign, target, _comment, attempt = _approved_comment_with_attempt(db_session)
    ChannelRulesService().create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist"},
    )
    db_session.commit()

    try:
        SenderService(
            config=SimpleNamespace(neuro_comment_tdlib_send_enabled=True)
        ).preflight_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    except NeuroConflictError as exc:
        assert exc.error_code == "CHANNEL_RULE_BLOCKED"
    else:
        raise AssertionError("blacklisted target passed send preflight")


def test_preflight_requires_ready_account_runtime(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    account = db_session.get(Account, attempt.account_id)
    assert account is not None
    account.runtime_state.runtime_health = "closed"
    db_session.commit()

    try:
        SenderService(
            config=SimpleNamespace(neuro_comment_tdlib_send_enabled=True)
        ).preflight_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    except NeuroConflictError as exc:
        assert exc.error_code == "ACCOUNT_RUNTIME_NOT_READY"
    else:
        raise AssertionError("unready account runtime passed send preflight")


def test_rate_limit_exceeded_denies_send_before_sender_call(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    limiter = DenyExceededLimiter()
    config = SimpleNamespace(
        neuro_comment_tdlib_send_enabled=True,
        neuro_comment_require_redis_limiter_for_send=True,
    )
    sender = FakeTelegramCommentSender(telegram_message_id="not-sent")

    result = SenderService(config=config, limiter=limiter, sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert limiter.called is True
    assert sender.calls == 0
    assert result.status == NeuroAttemptStatus.SKIPPED.value
    assert result.error_code == "RATE_LIMIT_DENIED"
    assert result.error_message == "account comments_per_hour limit exceeded"


def test_behavior_emulator_does_not_run_when_flag_absent(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    hook = _RecordingBehaviorHook()

    SenderService(
        config=_config_with_send_enabled(),
        sender=FakeTelegramCommentSender(),
        behavior_emulator_hook=hook,
    ).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert hook.calls == []
    assert (
        db_session.query(AccountBehaviorProfile).filter_by(account_id=attempt.account_id).count()
        == 0
    )


def test_behavior_emulator_prepares_plan_before_live_send_when_enabled(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    config = _config_with_send_enabled()
    config.behavior_emulator_live_send_enabled = True
    order: list[str] = []
    hook = _RecordingBehaviorHook(order)
    sender = _OrderingSender(order, telegram_message_id="telegram-behavior")

    sent = SenderService(
        config=config,
        sender=sender,
        behavior_emulator_hook=hook,
    ).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    event = (
        db_session.query(NeuroCommentEvent)
        .filter_by(attempt_id=attempt.id, event_type="behavior_emulator_live_send_prepared")
        .one()
    )
    profile = (
        db_session.query(AccountBehaviorProfile).filter_by(account_id=attempt.account_id).one()
    )
    plan = hook.calls[0]["plan"]
    assert sent.status == NeuroAttemptStatus.SENT.value
    assert order == ["behavior", "send"]
    assert sender.calls == 1
    assert event.data_json["behavior_profile_id"] == profile.id
    assert event.data_json["typing_fragment_count"] == len(plan.typing_fragments)
    assert event.data_json["decoy_action_count"] == len(plan.decoy_actions)


def test_behavior_emulator_not_run_when_rate_limit_denies_send(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    config = SimpleNamespace(
        neuro_comment_tdlib_send_enabled=True,
        neuro_comment_require_redis_limiter_for_send=True,
        behavior_emulator_live_send_enabled=True,
    )
    hook = _RecordingBehaviorHook()
    sender = FakeTelegramCommentSender()

    result = SenderService(
        config=config,
        limiter=DenyExceededLimiter(),
        sender=sender,
        behavior_emulator_hook=hook,
    ).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert result.status == NeuroAttemptStatus.SKIPPED.value
    assert result.error_code == "RATE_LIMIT_DENIED"
    assert hook.calls == []
    assert sender.calls == 0


def test_fake_sender_success_updates_attempt_and_counters(db_session) -> None:
    campaign, target, _comment, attempt = _approved_comment_with_attempt(db_session)
    config = type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "neuro_comment_require_redis_limiter_for_send": False,
        },
    )()
    sender = FakeTelegramCommentSender(telegram_message_id="telegram-1")

    sent = SenderService(config=config, sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    assert sent.status == NeuroAttemptStatus.SENT.value
    assert sent.telegram_message_id == "telegram-1"
    assert target.success_count == 1
    campaign_account = (
        db_session.query(NeuroCommentCampaignAccount).filter_by(campaign_id=campaign.id).one()
    )
    assert campaign_account.comments_sent == 1
    assert sender.calls == 1
    assert sender.last_reply_to_message_id == "99"


def test_manual_send_fails_if_discussion_message_id_is_missing(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    observed = db_session.get(NeuroCommentObservedPost, attempt.observed_post_id)
    assert observed is not None
    observed.discussion_message_id = None
    db_session.commit()
    config = type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "neuro_comment_require_redis_limiter_for_send": False,
        },
    )()

    with pytest.raises(NeuroConflictError) as exc_info:
        SenderService(config=config, sender=FakeTelegramCommentSender()).send_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    assert exc_info.value.error_code == "DISCUSSION_MESSAGE_NOT_RESOLVED"


def test_manual_send_prefers_observed_post_discussion_chat_id(db_session) -> None:
    _campaign, target, _comment, attempt = _approved_comment_with_attempt(db_session)
    observed = db_session.get(NeuroCommentObservedPost, attempt.observed_post_id)
    assert observed is not None
    target.discussion_chat_id = "456"
    observed.discussion_chat_id = "654"
    observed.discussion_message_id = "99"
    db_session.commit()
    config = type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "neuro_comment_require_redis_limiter_for_send": False,
        },
    )()
    sender = FakeTelegramCommentSender(telegram_message_id="telegram-1")

    SenderService(config=config, sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert sender.last_discussion_chat_id == "654"


def test_default_sender_uses_tdlib_sender_when_live_send_enabled() -> None:
    config = type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "tdlib_shared_library_path": settings.tdlib_shared_library_path,
        },
    )()

    sender = build_telegram_comment_sender(config)

    assert sender.__class__.__name__ == "TdlibTelegramCommentSender"


def test_tdlib_sender_uses_integer_chat_and_reply_ids() -> None:
    client = _RecordingTdlibClient(
        responses={
            "getMe": {"@type": "user", "id": 1},
            "sendMessage": {"@type": "message", "id": 777},
        }
    )
    sender = TdlibTelegramCommentSender(
        config=SimpleNamespace(
            tdlib_auth_timeout_seconds=0.1,
            tdlib_receive_timeout_seconds=0.1,
        ),
        client_factory=_RecordingTdlibFactory(client),
    )

    result = sender.send_comment(
        account_id="account-1",
        discussion_chat_id="456",
        reply_to_message_id="42",
        text="Hello",
    )

    send_query = client.queries[-1]
    assert result.telegram_message_id == "777"
    assert send_query["chat_id"] == 456
    assert send_query["reply_to_message_id"] == 42


def test_tdlib_sender_rejects_non_numeric_ids() -> None:
    sender = TdlibTelegramCommentSender(
        config=SimpleNamespace(
            tdlib_auth_timeout_seconds=0.1,
            tdlib_receive_timeout_seconds=0.1,
        ),
        client_factory=_RecordingTdlibFactory(
            _RecordingTdlibClient(responses={"getMe": {"@type": "user", "id": 1}})
        ),
    )

    try:
        sender.send_comment(
            account_id="account-1",
            discussion_chat_id="discussion-1",
            reply_to_message_id="42",
            text="Hello",
        )
    except TelegramCommentSendError as exc:
        assert exc.error_code == "CHAT_NOT_FOUND"
    else:
        raise AssertionError("non-numeric chat id was accepted")


def test_duplicate_sent_attempt_does_not_send_twice(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    attempt.status = NeuroAttemptStatus.SENT.value
    attempt.telegram_message_id = "already-sent"
    db_session.commit()
    config = type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "neuro_comment_require_redis_limiter_for_send": False,
        },
    )()
    sender = FakeTelegramCommentSender(telegram_message_id="telegram-2")

    sent = SenderService(config=config, sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert sent.telegram_message_id == "already-sent"
    assert sender.calls == 0


class _RaisingSender:
    """Sender that raises an arbitrary, non-TelegramCommentSendError exception
    to exercise the unexpected-exception cleanup path (F-002)."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc
        self.calls = 0

    def send_comment(self, **_kwargs):
        self.calls += 1
        raise self._exc


def _config_with_send_enabled():
    return type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "neuro_comment_require_redis_limiter_for_send": False,
        },
    )()


def test_send_attempt_non_flood_error_marks_failed(db_session) -> None:
    """F-001: non-FLOOD_WAIT TelegramCommentSendError must finalize the
    attempt as FAILED via _mark_send_error (not leave it in SENDING)."""
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    sender = FakeTelegramCommentSender(error=TelegramCommentSendError("CHAT_NOT_FOUND"))

    failed = SenderService(config=_config_with_send_enabled(), sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    assert failed.status == NeuroAttemptStatus.FAILED.value
    assert failed.failed_at is not None
    assert failed.error_code == "CHAT_NOT_FOUND"
    assert failed.error_message  # non-empty
    # And a NeuroCommentEvent was recorded (covers _mark_send_error wiring).
    events = (
        db_session.query(NeuroCommentEvent)
        .filter_by(attempt_id=attempt.id, event_type="comment_send_failed")
        .all()
    )
    assert len(events) == 1


def test_send_attempt_unexpected_exception_releases_reservations(db_session) -> None:
    """F-002: any non-TelegramCommentSendError exception must release the
    rate-limiter reservation and gate slot before re-raising."""
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    sender = _RaisingSender(RuntimeError("adapter blew up"))

    with pytest.raises(RuntimeError, match="adapter blew up"):
        SenderService(config=_config_with_send_enabled(), sender=sender).send_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    db_session.commit()

    refreshed = db_session.get(NeuroCommentAttempt, attempt.id)
    assert refreshed is not None
    assert refreshed.status == NeuroAttemptStatus.FAILED.value
    assert refreshed.failed_at is not None
    assert refreshed.error_code == "sender_unexpected_error"
    assert "RuntimeError" in (refreshed.error_message or "")
    # Audit event with error level was written.
    events = (
        db_session.query(NeuroCommentEvent)
        .filter_by(attempt_id=attempt.id, event_type="comment_send_unexpected_error")
        .all()
    )
    assert len(events) == 1


def test_send_attempt_unexpected_exception_re_raises(db_session) -> None:
    """F-002: the unexpected exception must propagate so worker/scheduler
    can escalate (sender does not silently swallow it)."""
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    sender = _RaisingSender(AttributeError("missing tdlib attr"))

    with pytest.raises(AttributeError):
        SenderService(config=_config_with_send_enabled(), sender=sender).send_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    # Sender was actually invoked (so the cleanup path ran).
    assert sender.calls == 1


def test_flood_wait_maps_to_attempt_status_and_cooldown(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    config = type(
        "Config",
        (),
        {
            "neuro_comment_tdlib_send_enabled": True,
            "neuro_comment_require_redis_limiter_for_send": False,
        },
    )()
    sender = FakeTelegramCommentSender(
        error=TelegramCommentSendError("FLOOD_WAIT", flood_wait_seconds=30)
    )

    failed = SenderService(config=config, sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    db_session.commit()

    assert failed.status == NeuroAttemptStatus.FLOOD_WAIT.value
    assert failed.flood_wait_seconds == 30
    assert failed.failed_at is not None


class _RecordingTdlibClient:
    def __init__(self, *, responses: dict[str, dict[str, object]]) -> None:
        self._responses = responses
        self.queries: list[dict[str, object]] = []
        self.close_calls = 0

    @property
    def client_id(self) -> int:
        return 1

    def send(self, query: dict[str, object]) -> None:
        self.queries.append(query)

    def receive(self, timeout_seconds: float) -> dict[str, object] | None:
        _ = timeout_seconds
        return None

    def send_query(self, payload: dict[str, object], timeout: float) -> dict[str, object]:
        _ = timeout
        self.queries.append(payload)
        return self._responses[str(payload["@type"])]

    def close(self) -> None:
        self.close_calls += 1


def test_tdlib_sender_closes_client_after_send() -> None:
    client = _RecordingTdlibClient(
        responses={
            "getMe": {"@type": "user", "id": 1},
            "sendMessage": {"@type": "message", "id": 777},
        }
    )
    sender = TdlibTelegramCommentSender(
        config=SimpleNamespace(
            tdlib_auth_timeout_seconds=0.1,
            tdlib_receive_timeout_seconds=0.1,
        ),
        client_factory=_RecordingTdlibFactory(client),
    )

    sender.send_comment(
        account_id="account-1",
        discussion_chat_id="456",
        reply_to_message_id="42",
        text="Hello",
    )

    assert client.close_calls == 1


def test_tdlib_sender_closes_client_after_send_error() -> None:
    client = _RecordingTdlibClient(
        responses={
            "getMe": {"@type": "user", "id": 1},
            "sendMessage": {"@type": "error", "message": "MESSAGE_NOT_FOUND"},
        }
    )
    sender = TdlibTelegramCommentSender(
        config=SimpleNamespace(
            tdlib_auth_timeout_seconds=0.1,
            tdlib_receive_timeout_seconds=0.1,
        ),
        client_factory=_RecordingTdlibFactory(client),
    )

    try:
        sender.send_comment(
            account_id="account-1",
            discussion_chat_id="456",
            reply_to_message_id="42",
            text="Hello",
        )
    except TelegramCommentSendError:
        pass
    else:
        raise AssertionError("TDLib send error was not raised")

    assert client.close_calls == 1


class _RecordingTdlibFactory:
    def __init__(self, client: _RecordingTdlibClient) -> None:
        self._client = client

    def create(self, account_id: str) -> _RecordingTdlibClient:
        _ = account_id
        return self._client
