"""Coverage for Task 45 / F-E001: account deletion cascade policy.

The migration 20260525_0054_account_safety_cascade re-creates every
safety-pipeline FK with an explicit ON DELETE behavior. The accompanying
service ``hard_delete_account`` mirrors that policy at the ORM layer so the
behavior is portable across Postgres (production) and SQLite (test factory).

Each test seeds a child row, runs ``hard_delete_account``, and verifies the
expected cascade vs. SET NULL behavior. A final test exercises tenant
isolation and the sensitive-audit invariant.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Account,
    AccountAuthAttempt,
    AccountBehaviorProfile,
    AccountGgrScore,
    AccountLifecycleEvent,
    AccountOperationLog,
    AccountQuarantine,
    AccountSafetyOverride,
    AccountStatusObservation,
    AccountState,
    BoughtOnboardingState,
    CrossModuleLoadBucket,
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    NeuroSafetyStatus,
    SensitiveAuditEvent,
    WarmupSession,
    WarmupStrategy,
    new_id,
    utc_now,
)
from app.services.account_lifecycle import hard_delete_account
from tests.helpers.factories import seed_account, seed_two_workspaces


def _ws() -> str:
    return DEFAULT_LOCAL_WORKSPACE_ID


def _delete(session, account: Account, reason: str = "test cleanup") -> dict:
    return hard_delete_account(
        session,
        account_id=account.id,
        workspace_id=_ws(),
        actor_user_id=None,
        reason=reason,
    )


def test_hard_delete_cascades_safety_pipeline_state(db_session) -> None:
    account = seed_account(db_session)
    db_session.add_all(
        [
            AccountQuarantine(
                id=new_id(),
                workspace_id=_ws(),
                account_id=account.id,
                reason="flood_wait",
                started_at=utc_now(),
                until=utc_now(),
            ),
            AccountStatusObservation(
                id=new_id(),
                workspace_id=_ws(),
                account_id=account.id,
                proxy_healthy=True,
                tdlib_authorized=True,
            ),
            CrossModuleLoadBucket(
                id=new_id(),
                workspace_id=_ws(),
                account_id=account.id,
                bucket_start=utc_now(),
            ),
            AccountGgrScore(
                id=new_id(),
                workspace_id=_ws(),
                account_id=account.id,
                score=5.0,
                bucket="medium",
            ),
            AccountBehaviorProfile(
                id=new_id(),
                workspace_id=_ws(),
                account_id=account.id,
                typo_rate_baseline=0.05,
                profile_view_probability_baseline=0.7,
                scroll_probability_baseline=0.3,
                message_deletion_probability_baseline=0.02,
                action_sequence_seed=42,
            ),
            AccountSafetyOverride(
                id=new_id(),
                account_id=account.id,
                operation="commenting",
                reason="manual override",
                allowed_until=utc_now(),
            ),
        ]
    )
    db_session.commit()

    report = _delete(db_session, account)

    for table in (
        "account_quarantines",
        "account_status_observations",
        "cross_module_load_buckets",
        "account_ggr_scores",
        "account_behavior_profile",
        "account_safety_override",
    ):
        assert report["cascade_deleted"][table] == 1, table
    # The parent row is gone.
    assert db_session.get(Account, account.id) is None


def test_hard_delete_cascades_bought_onboarding(db_session) -> None:
    account = seed_account(db_session, origin="bought")
    db_session.add(
        BoughtOnboardingState(
            id=new_id(),
            workspace_id=_ws(),
            account_id=account.id,
            current_step="rest_period",
            started_at=utc_now(),
            details_json={},
        )
    )
    db_session.commit()

    report = _delete(db_session, account)

    assert report["cascade_deleted"]["bought_onboarding_state"] == 1
    remaining = db_session.execute(
        select(BoughtOnboardingState).where(BoughtOnboardingState.account_id == account.id)
    ).first()
    assert remaining is None


def test_hard_delete_cascades_operation_log_and_auth_attempt(db_session) -> None:
    account = seed_account(db_session)
    db_session.add_all(
        [
            AccountOperationLog(
                id=new_id(),
                workspace_id=_ws(),
                account_id=account.id,
                operation_type="warmup_step",
                status="success",
                source="test",
                message="ok",
                metadata_json={},
            ),
            AccountAuthAttempt(
                id=new_id(),
                account_id=account.id,
                external_ref="+15550000001",
                attempt_kind="register",
                outcome="success",
            ),
        ]
    )
    db_session.commit()

    report = _delete(db_session, account)

    assert report["cascade_deleted"]["account_operation_log"] == 1
    assert report["cascade_deleted"]["account_auth_attempt"] == 1


def test_hard_delete_cascades_warmup_session(db_session) -> None:
    account = seed_account(db_session, account_state=AccountState.EXECUTION_USABLE)
    strategy = WarmupStrategy(id=new_id(), workspace_id=_ws(), name="default-strategy")
    db_session.add(strategy)
    db_session.flush()
    db_session.add(
        WarmupSession(
            id=new_id(),
            workspace_id=_ws(),
            account_id=account.id,
            strategy_id=strategy.id,
            status="draft",
        )
    )
    db_session.commit()

    report = _delete(db_session, account)

    assert report["cascade_deleted"]["warmup_session"] == 1


def test_hard_delete_cascades_lifecycle_events(db_session) -> None:
    account = seed_account(db_session)
    db_session.add(
        AccountLifecycleEvent(
            id=new_id(),
            workspace_id=_ws(),
            account_id=account.id,
            event_type="account.created",
            payload_json={},
        )
    )
    db_session.commit()

    report = _delete(db_session, account)

    assert report["cascade_deleted"]["account_lifecycle_event"] == 1


def test_hard_delete_set_null_neuro_comment_attempts(db_session) -> None:
    account = seed_account(db_session)
    campaign = NeuroCommentCampaign(
        id=new_id(),
        workspace_id=_ws(),
        name="cascade-test",
        status="draft",
    )
    db_session.add(campaign)
    db_session.flush()
    comment = NeuroCommentGeneratedComment(
        id=new_id(),
        campaign_id=campaign.id,
        account_id=account.id,
        generated_text="hello",
        safety_status=NeuroSafetyStatus.PASSED.value,
    )
    db_session.add(comment)
    db_session.flush()
    attempt = NeuroCommentAttempt(
        id=new_id(),
        campaign_id=campaign.id,
        generated_comment_id=comment.id,
        account_id=account.id,
    )
    db_session.add(attempt)
    db_session.commit()

    report = _delete(db_session, account)

    assert report["set_null_updated"]["neuro_comment_attempts"] == 1
    db_session.refresh(attempt)
    assert attempt.account_id is None
    # Audit row itself preserved.
    db_session.refresh(comment)
    assert comment.account_id is None
    assert report["set_null_updated"]["neuro_comment_generated_comments"] == 1


def test_hard_delete_set_null_neuro_comment_events(db_session) -> None:
    account = seed_account(db_session)
    campaign = NeuroCommentCampaign(
        id=new_id(),
        workspace_id=_ws(),
        name="cascade-events",
        status="draft",
    )
    db_session.add(campaign)
    db_session.flush()
    event = NeuroCommentEvent(
        id=new_id(),
        workspace_id=_ws(),
        campaign_id=campaign.id,
        account_id=account.id,
        event_type="approval_expired",
        message="expired",
    )
    db_session.add(event)
    db_session.commit()

    report = _delete(db_session, account)

    assert report["set_null_updated"]["neuro_comment_events"] == 1
    db_session.refresh(event)
    assert event.account_id is None


def test_hard_delete_records_sensitive_audit_with_snapshot(db_session) -> None:
    account = seed_account(db_session)
    db_session.add(
        AccountQuarantine(
            id=new_id(),
            workspace_id=_ws(),
            account_id=account.id,
            reason="flood_wait",
            started_at=utc_now(),
            until=utc_now(),
        )
    )
    db_session.commit()
    account_id = account.id

    _delete(db_session, account, reason="GDPR purge")

    audit_row = db_session.execute(
        select(SensitiveAuditEvent).where(SensitiveAuditEvent.action == "account.deleted")
    ).scalar_one()
    # Audit retention: row remains and references the now-deleted account by id.
    assert audit_row.account_id == account_id
    assert audit_row.reason == "GDPR purge"
    assert audit_row.metadata_json["cascade_deleted"]["account_quarantines"] == 1


def test_hard_delete_cross_tenant_is_rejected(db_session) -> None:
    home_ws, foreign_ws = seed_two_workspaces(db_session)
    foreign_account = seed_account(db_session, workspace_id=foreign_ws)

    with pytest.raises(ValueError, match="account not found"):
        hard_delete_account(
            db_session,
            account_id=foreign_account.id,
            workspace_id=home_ws,
            actor_user_id=None,
            reason="cross-tenant probe",
        )

    # Foreign account still present.
    assert db_session.get(Account, foreign_account.id) is not None
