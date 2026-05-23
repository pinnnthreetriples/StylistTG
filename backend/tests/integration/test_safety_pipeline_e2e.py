from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from freezegun import freeze_time

from app.main import app
from app.models import (
    AccountGgrScore,
    AccountProfileState,
    AccountProxy,
    AccountQuarantine,
    AccountState,
    AccountStatusObservation,
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    NeuroAttemptStatus,
    NeuroCommentCampaignAccount,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    SensitiveAuditEvent,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    Workspace,
    new_id,
    utc_now,
)
from app.services.account_quarantine import handle_flood_wait
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from app.services.account_status_monitor import (
    AccountStatusMonitor,
    AccountStatusProbeResult,
)
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.bought_account_onboarding import process_rest_period_ggr_check
from app.services.cross_module_load_tracker import current_load, track
from app.services.neuro_commenting.approval_service import ApprovalService
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.jobs import observe_target
from app.services.neuro_commenting.live_readiness_service import LiveReadinessService
from app.services.neuro_commenting.sender_service import FakeTelegramCommentSender, SenderService
from app.services.neuro_commenting.target_service import TargetService
from app.services.workspace_safety_policy import get_workspace_safety_policy
from tests._fakes.fake_tdlib_runtime import FakeTdlibRuntime
from tests.helpers.factories import seed_account


WORKSPACE = DEFAULT_LOCAL_WORKSPACE_ID
_FROZEN_NOW = datetime(2026, 5, 23, 10, 0, tzinfo=UTC)


class _Probe:
    def __init__(self, results: list[AccountStatusProbeResult]) -> None:
        self._results = results

    def check(self, account) -> AccountStatusProbeResult:
        return self._results.pop(0)


def _auth(role: str = "admin") -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=WORKSPACE,
        role=role,
        auth_source="test",
    )


def _send_config() -> SimpleNamespace:
    return SimpleNamespace(
        neuro_comment_tdlib_send_enabled=True,
        neuro_comment_require_redis_limiter_for_send=False,
    )


def _scheduled_noop(*args, **kwargs) -> bool:
    return True


def _ready_account(
    db_session,
    *,
    external_ref: str,
    origin: str = "imported",
    with_warmup: bool = True,
):
    account = seed_account(
        db_session,
        external_ref=external_ref,
        origin=origin,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.created_at = _FROZEN_NOW - timedelta(days=30)
    account.pinned_channel_ref = "@safety_e2e"
    workspace = db_session.get(Workspace, WORKSPACE)
    workspace.safety_pipeline_v2_enabled = True
    policy = get_workspace_safety_policy(db_session, workspace_id=WORKSPACE, create_if_missing=True)
    policy.mode = "balanced"
    policy.min_account_age_hours = 24
    policy.min_warmup_days = 3
    policy.require_healthy_proxy = True
    policy.require_warmup_before_commenting = True
    policy.auto_pause_on_flood_wait_count = 3
    account.proxy = AccountProxy(
        account_id=account.id,
        proxy_type="socks5",
        host="127.0.0.1",
        port=1080,
        status="tdlib_working",
    )
    db_session.add(
        AccountProfileState(
            account_id=account.id,
            first_name="Safety",
            bio="Long enough integration profile bio",
            username=f"safety_{new_id()[:8]}",
            profile_photo_asset_id="00000000-0000-4000-8000-000000000301",
        )
    )
    if with_warmup:
        _make_warmup(db_session, account, status=WarmupStatus.COMPLETED.value, current_day=3)
    _make_ggr(db_session, account, score=8.5, bucket="strong")
    db_session.commit()
    db_session.refresh(account)
    return account


def _make_warmup(db_session, account, *, status: str, current_day: int) -> None:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=account.workspace_id,
        name=f"safety-e2e-{new_id()[:6]}",
        tier_limits_json={},
        target_channels_json=[],
        duration_days=14,
    )
    db_session.add(strategy)
    db_session.flush()
    db_session.add(
        WarmupSession(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            strategy_id=strategy.id,
            status=status,
            current_day=current_day,
            duration_days=14,
            completed_at=utc_now() if status == WarmupStatus.COMPLETED.value else None,
        )
    )


def _make_ggr(db_session, account, *, score: float, bucket: str) -> None:
    db_session.query(AccountGgrScore).filter(AccountGgrScore.account_id == account.id).delete()
    db_session.add(
        AccountGgrScore(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            score=score,
            bucket=bucket,
            breakdown_json={"fraud_score": 0.1},
            last_calculated_at=utc_now(),
            next_calculation_at=utc_now() + timedelta(hours=6),
        )
    )


def _campaign_with_target(db_session, account, *, name: str):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
        payload={
            "name": name,
            "dry_run": False,
            "mode": "all_posts",
            "send_mode": "manual_approval",
        },
    )
    campaign.status = "running"
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
        payload={
            "channel_ref": f"@{name.lower().replace(' ', '_')}",
            "channel_id": f"{name}-channel",
            "discussion_chat_id": f"{name}-discussion",
            "title": name,
            "username": name.lower().replace(" ", "_"),
        },
    )
    db_session.commit()
    return campaign, target


def _approved_attempt_from_fake_tdlib(db_session, account, *, name: str):
    campaign, target = _campaign_with_target(db_session, account, name=name)
    runtime = FakeTdlibRuntime()
    runtime.seed_metadata_from_target(target)
    runtime.observer.add_post(
        source_chat_id=target.channel_id or "source-chat",
        source_message_id=f"{name}-post-1",
        post_text="Safety pipeline E2E post",
        language="en",
    )
    observed = observe_target(
        db_session,
        campaign_id=campaign.id,
        target_id=target.id,
        workspace_id=WORKSPACE,
        observer=runtime.build_observer(),
    )[0]
    observed.discussion_message_id = f"{name}-discussion-message"
    observed.discussion_resolved_at = utc_now()
    comment = (
        db_session.query(NeuroCommentGeneratedComment)
        .filter(NeuroCommentGeneratedComment.observed_post_id == observed.id)
        .one()
    )
    _approved, attempt = ApprovalService().approve_comment(
        db_session,
        comment_id=comment.id,
        workspace_id=WORKSPACE,
        actor_user_id="user-1",
    )
    db_session.commit()
    return campaign, target, attempt


def _gate(db_session, account):
    return AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )


@freeze_time(_FROZEN_NOW)
def test_live_readiness_blocks_unwarmed_account_through_gate(db_session) -> None:
    account = _ready_account(db_session, external_ref="+15550380001", with_warmup=False)
    campaign, _target = _campaign_with_target(db_session, account, name="No Warmup E2E")

    readiness = LiveReadinessService(config=_send_config(), limiter_ready=True).check(
        db_session,
        campaign_id=campaign.id,
        workspace_id=WORKSPACE,
    )

    gate_check = next(check for check in readiness.checks if check.code == "account_safety_blocked")
    assert {
        "ready": readiness.ready,
        "severity": gate_check.severity,
        "reason_codes": [reason["code"] for reason in gate_check.details["reasons"]],
    } == {
        "ready": False,
        "severity": "blocker",
        "reason_codes": ["no_warmup"],
    }


@freeze_time(_FROZEN_NOW)
def test_status_monitor_auto_pauses_campaign_and_sender_gate_blocks(db_session) -> None:
    account = _ready_account(db_session, external_ref="+15550380002")
    _campaign, _target, attempt = _approved_attempt_from_fake_tdlib(
        db_session, account, name="Auto Pause E2E"
    )
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(False, "10.0.0.1", True, "Pixel 7"),
                AccountStatusProbeResult(False, "10.0.0.2", True, "Pixel 7"),
                AccountStatusProbeResult(False, "10.0.0.3", True, "Pixel 7"),
                AccountStatusProbeResult(False, "10.0.0.4", True, "Pixel 7"),
            ]
        )
    )

    for _ in range(4):
        monitor.observe_account(
            db_session, account_id=account.id, workspace_id=account.workspace_id
        )
    campaign_account = (
        db_session.query(NeuroCommentCampaignAccount)
        .filter_by(campaign_id=attempt.campaign_id, account_id=attempt.account_id)
        .one()
    )
    campaign_account.status = "active"
    result = SenderService(config=_send_config(), sender=FakeTelegramCommentSender()).send_attempt(
        db_session,
        attempt_id=attempt.id,
        workspace_id=WORKSPACE,
    )

    event_types = {
        event.event_type
        for event in db_session.query(NeuroCommentEvent)
        .filter(NeuroCommentEvent.account_id == account.id)
        .all()
    }
    assert {
        "auto_pause_logged": "account_auto_paused" in event_types,
        "status": result.status,
        "error_code": result.error_code,
        "blocked_event": "neuro_comment_send_blocked_by_gate" in event_types,
    } == {
        "auto_pause_logged": True,
        "status": NeuroAttemptStatus.SKIPPED.value,
        "error_code": "ACCOUNT_SAFETY_BLOCKED",
        "blocked_event": True,
    }


@freeze_time(_FROZEN_NOW)
def test_bought_account_rest_period_releases_after_strong_ggr_and_gate_allows(
    app_client, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.bought_account_onboarding.schedule_bought_onboarding_action",
        _scheduled_noop,
    )
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("admin")
    account = _ready_account(db_session, external_ref="+15550380003", origin="bought")

    response = app_client.post(f"/api/accounts/{account.id}/bought-onboarding/start")
    state = process_rest_period_ggr_check(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
    )
    verdict = _gate(db_session, account)

    quarantine = db_session.query(AccountQuarantine).filter_by(account_id=account.id).one()
    assert {
        "status_code": response.status_code,
        "quarantine_reason": quarantine.reason,
        "released": quarantine.released_at is not None,
        "state_step": state.current_step,
        "gate_severity": verdict.severity,
        "gate_eligible": verdict.eligible,
    } == {
        "status_code": 201,
        "quarantine_reason": "bought_rest_period",
        "released": True,
        "state_step": "completed",
        "gate_severity": "ok",
        "gate_eligible": True,
    }


@freeze_time(_FROZEN_NOW)
def test_flood_wait_quarantine_requires_admin_override_before_gate_allows(
    app_client, db_session
) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("admin")
    account = _ready_account(db_session, external_ref="+15550380004")
    quarantine = handle_flood_wait(
        db_session,
        account_id=account.id,
        workspace_id=account.workspace_id,
        flood_wait_seconds=300,
        source_attempt_id="attempt-flood-e2e",
    )

    blocked = _gate(db_session, account)
    response = app_client.post(
        f"/api/accounts/{account.id}/quarantine/admin-override",
        json={"reason": "operator verified false positive"},
    )
    allowed = _gate(db_session, account)

    db_session.refresh(quarantine)
    audit = db_session.query(SensitiveAuditEvent).filter_by(account_id=account.id).one()
    assert {
        "initial": blocked.severity,
        "override_status": response.status_code,
        "released": quarantine.released_at is not None,
        "audit_action": audit.action,
        "final": allowed.severity,
        "final_eligible": allowed.eligible,
    } == {
        "initial": "blocked",
        "override_status": 200,
        "released": True,
        "audit_action": "quarantine.admin_override_released",
        "final": "ok",
        "final_eligible": True,
    }


@freeze_time(_FROZEN_NOW)
def test_cross_module_load_warns_at_balanced_threshold_then_blocks(db_session) -> None:
    account = _ready_account(db_session, external_ref="+15550380005")

    track(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        module="warmup",
        count=10,
    )
    track(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        module="commenting",
        count=10,
    )
    warning = _gate(db_session, account)
    track(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        module="commenting",
        count=5,
    )
    blocked = _gate(db_session, account)

    assert {
        "load": current_load(
            db_session, workspace_id=account.workspace_id, account_id=account.id
        ).last_hour,
        "warning": warning.severity,
        "warning_reason": [reason.code for reason in warning.reasons],
        "blocked": blocked.severity,
        "blocked_reason": [reason.code for reason in blocked.reasons],
    } == {
        "load": 25,
        "warning": "warning",
        "warning_reason": ["cross_module_overload"],
        "blocked": "blocked",
        "blocked_reason": ["cross_module_overload"],
    }


@freeze_time(_FROZEN_NOW)
def test_ip_change_cooldown_warns_then_expires_to_ok(db_session) -> None:
    account = _ready_account(db_session, external_ref="+15550380006")
    monitor = AccountStatusMonitor(
        probe=_Probe(
            [
                AccountStatusProbeResult(True, "10.0.0.1", True, "Pixel 7"),
                AccountStatusProbeResult(True, "10.0.0.2", True, "Pixel 7"),
            ]
        )
    )

    monitor.observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)
    monitor.observe_account(db_session, account_id=account.id, workspace_id=account.workspace_id)
    warning = _gate(db_session, account)
    latest = (
        db_session.query(AccountStatusObservation)
        .filter_by(account_id=account.id)
        .order_by(AccountStatusObservation.observed_at.desc())
        .first()
    )
    latest.observed_at = _FROZEN_NOW - timedelta(minutes=31)
    db_session.commit()
    allowed = _gate(db_session, account)

    assert {
        "warning": warning.severity,
        "warning_reasons": [reason.code for reason in warning.reasons],
        "after_expiry": allowed.severity,
        "eligible_after_expiry": allowed.eligible,
    } == {
        "warning": "warning",
        "warning_reasons": ["ip_change_cooldown"],
        "after_expiry": "ok",
        "eligible_after_expiry": True,
    }


@freeze_time(_FROZEN_NOW)
def test_pipeline_uses_account_safety_gate_at_least_five_times(db_session, monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    original = AccountSafetyGate.evaluate

    def counted(self, session, *, workspace_id: str, account_id: str, intent: str):
        calls.append((account_id, intent))
        return original(
            self,
            session,
            workspace_id=workspace_id,
            account_id=account_id,
            intent=intent,
        )

    monkeypatch.setattr(AccountSafetyGate, "evaluate", counted)
    account = _ready_account(db_session, external_ref="+15550380007")

    for _ in range(5):
        _gate(db_session, account)

    assert len(calls) >= 5
