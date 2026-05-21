from __future__ import annotations

from datetime import timedelta

from app.models import (
    AccountGgrScore,
    AccountProfileState,
    AccountProxy,
    AccountQuarantine,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    Workspace,
    new_id,
    utc_now,
)
from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache
from app.services.workspace_safety_policy import get_workspace_safety_policy
from tests.helpers.factories import seed_account


def test_default_false_uses_legacy_shim_without_full_v2_reasons(db_session) -> None:
    account = _ready_account(db_session)
    account.created_at = utc_now()
    db_session.commit()

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.eligible is True
    assert verdict.severity == "ok"
    assert {reason.code for reason in verdict.reasons} == set()


def test_flag_true_keeps_full_v2_verdict(db_session) -> None:
    account = _ready_account(db_session)
    workspace = db_session.get(Workspace, account.workspace_id)
    workspace.safety_pipeline_v2_enabled = True
    account.created_at = utc_now()
    db_session.commit()

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.eligible is False
    assert "age_too_low" in {reason.code for reason in verdict.reasons}


def test_legacy_shim_blocks_unhealthy_proxy(db_session) -> None:
    account = _ready_account(db_session)
    account.proxy.status = "failed"
    db_session.commit()

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.eligible is False
    assert verdict.severity == "blocked"
    assert {reason.code for reason in verdict.reasons} == {"proxy_unhealthy"}


def test_legacy_shim_blocks_active_quarantine(db_session) -> None:
    account = _ready_account(db_session)
    db_session.add(
        AccountQuarantine(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            reason="manual",
            started_at=utc_now(),
            until=utc_now() + timedelta(hours=24),
            metadata_json={},
        )
    )
    db_session.commit()

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.eligible is False
    assert {reason.code for reason in verdict.reasons} == {"active_quarantine"}


def test_legacy_shim_blocks_missing_warmup_for_commenting(db_session) -> None:
    account = _ready_account(db_session)
    db_session.query(WarmupSession).filter(WarmupSession.account_id == account.id).delete()
    db_session.commit()

    verdict = AccountSafetyGate(cache=InMemorySafetyGateCache()).evaluate(
        db_session,
        workspace_id=account.workspace_id,
        account_id=account.id,
        intent="commenting",
    )

    assert verdict.eligible is False
    assert {reason.code for reason in verdict.reasons} == {"no_warmup"}


def _ready_account(db_session):
    account = seed_account(
        db_session,
        external_ref=f"+1555010{new_id()[:4]}",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.created_at = utc_now() - timedelta(days=30)
    account.pinned_channel_ref = "@channel"
    policy = get_workspace_safety_policy(
        db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID, create_if_missing=True
    )
    policy.min_account_age_hours = 24
    policy.min_warmup_days = 3
    policy.require_healthy_proxy = True
    policy.require_warmup_before_commenting = True
    db_session.add(
        AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            host="127.0.0.1",
            port=1080,
            status="tdlib_working",
        )
    )
    db_session.add(
        AccountProfileState(
            account_id=account.id,
            first_name="Anna",
            bio="Long enough profile bio",
            username="anna",
            profile_photo_asset_id="00000000-0000-4000-8000-000000000201",
        )
    )
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=account.workspace_id,
        name=f"strategy-{new_id()}",
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
            status=WarmupStatus.COMPLETED.value,
            current_day=3,
            duration_days=14,
            completed_at=utc_now(),
        )
    )
    db_session.add(
        AccountGgrScore(
            id=new_id(),
            workspace_id=account.workspace_id,
            account_id=account.id,
            score=8.0,
            bucket="strong",
            breakdown_json={"fraud_score": 0.1},
            last_calculated_at=utc_now(),
            next_calculation_at=utc_now() + timedelta(hours=6),
        )
    )
    db_session.commit()
    db_session.refresh(account)
    return account
