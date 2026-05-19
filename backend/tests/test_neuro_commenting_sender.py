from __future__ import annotations

from types import SimpleNamespace

from app.config import settings
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountState,
    NeuroCommentCampaignAccount,
    NeuroAttemptStatus,
    NeuroCommentAttempt,
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
    build_telegram_comment_sender,
)
from app.services.neuro_commenting.tdlib_comment_sender import TdlibTelegramCommentSender
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account


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

    try:
        SenderService(config=settings).send_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    except Exception as exc:
        assert getattr(exc, "error_code", "") == "NEURO_COMMENT_SEND_DISABLED"
    else:
        raise AssertionError("manual send did not fail closed")


def test_limiter_gate_denied_does_not_construct_tdlib_sender(db_session) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    config = SimpleNamespace(
        neuro_comment_tdlib_send_enabled=True,
        neuro_comment_require_redis_limiter_for_send=True,
    )

    try:
        SenderService(config=config).send_attempt(
            db_session,
            attempt_id=attempt.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    except Exception as exc:
        assert getattr(exc, "error_code", "") == "NEURO_COMMENT_RATE_LIMITER_NOT_READY"
    else:
        raise AssertionError("limiter gate did not fail closed")


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
    assert sender.last_reply_to_message_id == "42"


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
        return None


class _RecordingTdlibFactory:
    def __init__(self, client: _RecordingTdlibClient) -> None:
        self._client = client

    def create(self, account_id: str) -> _RecordingTdlibClient:
        _ = account_id
        return self._client
