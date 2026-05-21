from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.config import Settings
from app.contracts.safety_gate import SafetyGateReason, SafetyGateVerdict
from app.models import (
    AccountQuarantine,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroAttemptStatus,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroCommentObservedPost,
    NeuroSafetyStatus,
    WarmupExecutionMode,
    WarmupPresetKind,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
    utc_now,
)
from app.modules.account_editing import service as account_editing_service
from app.modules.warmup import dispatcher as warmup_dispatcher
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.live_readiness_service import LiveReadinessService
from app.services.neuro_commenting.sender_service import (
    FakeTelegramCommentSender,
    SenderService,
)
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account, seed_account_with_profile


def test_live_readiness_blocks_when_gate_reports_incomplete_warmup(db_session, monkeypatch) -> None:
    account, campaign, _target = _ready_campaign(db_session)

    def fake_gate(session, *, workspace_id: str, account_id: str, intent: str):
        assert (workspace_id, account_id, intent) == (
            DEFAULT_LOCAL_WORKSPACE_ID,
            account.id,
            "commenting",
        )
        return _verdict(account.id, intent="commenting", code="warmup_incomplete")

    monkeypatch.setattr(
        "app.services.neuro_commenting.live_readiness_service.evaluate_safety_gate",
        fake_gate,
        raising=False,
    )

    readiness = LiveReadinessService(config=_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    gate_check = next(check for check in readiness.checks if check.code == "account_safety_blocked")
    assert {
        "ready": readiness.ready,
        "severity": gate_check.severity,
        "reason_codes": [reason["code"] for reason in gate_check.details["reasons"]],
    } == {
        "ready": False,
        "severity": "blocker",
        "reason_codes": ["warmup_incomplete"],
    }


def test_sender_preflight_blocks_before_send_when_gate_blocks(db_session, monkeypatch) -> None:
    _campaign, _target, _comment, attempt = _approved_comment_with_attempt(db_session)
    sender = FakeTelegramCommentSender()

    def fake_gate(session, *, workspace_id: str, account_id: str, intent: str):
        assert (workspace_id, account_id, intent) == (
            DEFAULT_LOCAL_WORKSPACE_ID,
            attempt.account_id,
            "commenting",
        )
        return _verdict(account_id, intent="commenting", code="fraud_score_high")

    monkeypatch.setattr(
        "app.services.neuro_commenting.sender_service.evaluate_safety_gate",
        fake_gate,
        raising=False,
    )

    result = SenderService(config=_send_config(), sender=sender).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    event = (
        db_session.query(NeuroCommentEvent)
        .filter_by(event_type="neuro_comment_send_blocked_by_gate")
        .one()
    )
    assert {
        "status": result.status,
        "error_code": result.error_code,
        "sender_calls": sender.calls,
        "event_reasons": event.data_json["reasons"],
    } == {
        "status": NeuroAttemptStatus.SKIPPED.value,
        "error_code": "ACCOUNT_SAFETY_BLOCKED",
        "sender_calls": 0,
        "event_reasons": ["fraud_score_high"],
    }


def test_warmup_dispatch_pauses_when_gate_blocks(db_session, monkeypatch) -> None:
    warmup_session = _warmup_session(db_session)

    def fake_gate(session, *, workspace_id: str, account_id: str, intent: str):
        assert (workspace_id, account_id, intent) == (
            DEFAULT_LOCAL_WORKSPACE_ID,
            warmup_session.account_id,
            "warmup",
        )
        return _verdict(warmup_session.account_id, intent="warmup", code="proxy_unhealthy")

    monkeypatch.setattr(
        "app.modules.warmup.dispatcher.evaluate_safety_gate",
        fake_gate,
        raising=False,
    )

    processed = warmup_dispatcher.process_due_warmup_dispatches(
        db_session,
        worker_id="worker-1",
        now=datetime(2026, 6, 1, 12, tzinfo=UTC),
    )

    db_session.refresh(warmup_session)
    event_types = [event.event_type for event in warmup_session.events]
    assert {
        "processed": processed,
        "status": warmup_session.status,
        "next_micro_session_at": warmup_session.next_micro_session_at,
        "event_logged": "warmup_dispatch_blocked_by_gate" in event_types,
    } == {
        "processed": 1,
        "status": WarmupStatus.PAUSED_RISK.value,
        "next_micro_session_at": None,
        "event_logged": True,
    }


def test_editing_preview_adds_gate_blocking_error(db_session, monkeypatch) -> None:
    account = seed_account_with_profile(db_session)

    def fake_gate(session, *, workspace_id: str, account_id: str, intent: str):
        assert (workspace_id, account_id, intent) == (account.workspace_id, account.id, "editing")
        return _verdict(account.id, intent="editing", code="terminal_status")

    monkeypatch.setattr(
        "app.modules.account_editing.service.evaluate_safety_gate",
        fake_gate,
        raising=False,
    )

    preview = account_editing_service.build_account_update_preview(
        db_session,
        account_id=account.id,
        desired_state={"profile": {"name": "Stylist TG"}},
        workspace_id=account.workspace_id,
        config=Settings(profile_job_cooldown_seconds=0),
    )

    assert preview["can_create_job"] is False
    assert any(error.startswith("safety_gate_blocked:") for error in preview["blocking_errors"])


def test_active_quarantine_blocks_all_gate_intents(db_session) -> None:
    account = seed_account(
        db_session,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    db_session.add(
        AccountQuarantine(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            reason="manual",
            started_at=utc_now(),
            until=utc_now() + timedelta(hours=1),
            metadata_json={},
        )
    )
    db_session.commit()

    verdicts = [
        AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
            db_session,
            workspace_id=account.workspace_id,
            account_id=account.id,
            intent=intent,
        )
        for intent in ("editing", "warmup", "commenting")
    ]

    assert {verdict.intent: verdict.severity for verdict in verdicts} == {
        "editing": "blocked",
        "warmup": "blocked",
        "commenting": "blocked",
    }
    assert all(
        "active_quarantine" in {reason.code for reason in verdict.reasons} for verdict in verdicts
    )


def _config(*, send_enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(neuro_comment_tdlib_send_enabled=send_enabled)


def _send_config() -> SimpleNamespace:
    return SimpleNamespace(
        neuro_comment_tdlib_send_enabled=True,
        neuro_comment_require_redis_limiter_for_send=False,
    )


def _verdict(account_id: str, *, intent: str, code: str) -> SafetyGateVerdict:
    return SafetyGateVerdict(
        account_id=account_id,
        intent=intent,
        eligible=False,
        severity="blocked",
        reasons=[
            SafetyGateReason(
                code=code,
                severity="blocked",
                message=f"{code} blocks the account.",
                metadata={"source": "test"},
            )
        ],
        ggr_score=8.0,
        checked_at=utc_now(),
        cache_ttl_seconds=60,
    )


def _ready_campaign(db_session):
    account = seed_account(
        db_session,
        external_ref="+15550117001",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Gate readiness", "dry_run": False, "send_mode": "manual_approval"},
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
        payload={"channel_ref": "@example", "discussion_chat_id": "discussion-1"},
    )
    db_session.commit()
    return account, campaign, target


def _approved_comment_with_attempt(db_session):
    account, campaign, target = _ready_campaign(db_session)
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
        generated_text="Interesting.",
        final_text="Interesting.",
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


def _warmup_session(db_session) -> WarmupSession:
    account = seed_account(
        db_session,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Gate {new_id()[:6]}",
        description="Gate test",
        tier_limits_json={"cadence_hours": 24, "profile_required": True},
        target_channels_json=[],
        is_preset=False,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        preset_kind=WarmupPresetKind.STANDARD.value,
        duration_days=3,
        daily_action_limits_json={"1": {"feed_read": 1}},
        session_window_config_json={"micro_sessions_per_day": {"min": 1, "max": 1}},
        ui_summary_json={},
    )
    db_session.add(strategy)
    db_session.flush()
    warmup_session = WarmupSession(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        strategy_id=strategy.id,
        status=WarmupStatus.SCHEDULED.value,
        execution_mode=WarmupExecutionMode.SHADOW.value,
        current_day=0,
        duration_days=3,
        next_micro_session_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
        next_step_at=datetime(2026, 6, 1, 12, tzinfo=UTC),
        daily_counters_json={},
        timezone="UTC",
    )
    db_session.add(warmup_session)
    db_session.commit()
    return warmup_session
