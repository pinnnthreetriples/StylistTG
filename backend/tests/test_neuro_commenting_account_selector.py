from __future__ import annotations

from datetime import UTC, datetime

from app.models import AccountState, DEFAULT_LOCAL_WORKSPACE_ID, NeuroCommentCampaignAccount, new_id
from app.services.neuro_commenting.account_health_service import AccountHealthService
from app.services.neuro_commenting.account_selector import (
    AccountReadinessProvider,
    AccountSelector,
)
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import CampaignService
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.target_service import TargetService
from tests.helpers.factories import seed_account, seed_two_workspaces


class FakeReadiness(AccountReadinessProvider):
    def __init__(self, ready: set[str]) -> None:
        self.ready = ready

    def is_ready(self, account_id: str) -> bool:
        return account_id in self.ready


class FakeRng:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value

    def random(self) -> float:
        return self.value

    def choice(self, items):
        return items[-1]


class DenyRateLimiter:
    def reserve(self, scope):
        return type(
            "Reservation",
            (),
            {
                "allowed": False,
                "reservation_id": None,
                "reason": "account comments_per_hour limit exceeded",
            },
        )()

    def rollback(self, reservation):  # pragma: no cover - denied reservations are not rolled back
        raise AssertionError("rollback should not be called")


def _campaign(db_session, strategy: str = "round_robin"):
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Rotation", "rotation_strategy": strategy},
    )
    target = TargetService().add_target(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"channel_ref": "@target"},
    )
    return campaign, target


def _add_account(db_session, campaign, external_ref: str, order: int, weight: int = 1):
    account = seed_account(
        db_session,
        external_ref=external_ref,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign_account = CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        rotation_order=order,
        rotation_weight=weight,
    )
    return account, campaign_account


def test_round_robin_respects_rotation_order_and_skips_cooldown(db_session) -> None:
    campaign, target = _campaign(db_session)
    account_a, campaign_account_a = _add_account(db_session, campaign, "+15550104001", 2)
    account_b, campaign_account_b = _add_account(db_session, campaign, "+15550104002", 1)
    campaign_account_b.cooldown_until = datetime(2099, 1, 1, tzinfo=UTC)
    db_session.commit()

    result = AccountSelector(
        readiness_provider=FakeReadiness({account_a.id, account_b.id})
    ).select_account(campaign, [campaign_account_a, campaign_account_b], target)

    assert result.account == campaign_account_a
    assert [skip.reason for skip in result.skipped] == ["cooldown"]


def test_weighted_least_used_and_random_strategies(db_session) -> None:
    campaign, target = _campaign(db_session, strategy="weighted")
    account_a, campaign_account_a = _add_account(db_session, campaign, "+15550104003", 1, 1)
    account_b, campaign_account_b = _add_account(db_session, campaign, "+15550104004", 2, 3)

    weighted = AccountSelector(
        readiness_provider=FakeReadiness({account_a.id, account_b.id}), rng=FakeRng(0.9)
    ).select_account(campaign, [campaign_account_a, campaign_account_b], target)
    campaign.rotation_strategy = "least_used"
    campaign_account_a.comments_sent = 5
    campaign_account_b.comments_sent = 1
    least_used = AccountSelector(
        readiness_provider=FakeReadiness({account_a.id, account_b.id})
    ).select_account(campaign, [campaign_account_a, campaign_account_b], target)
    campaign.rotation_strategy = "random"
    campaign_account_b.status = "paused"
    random_result = AccountSelector(
        readiness_provider=FakeReadiness({account_a.id, account_b.id}), rng=FakeRng()
    ).select_account(campaign, [campaign_account_a, campaign_account_b], target)

    assert weighted.account == campaign_account_b
    assert least_used.account == campaign_account_b
    assert random_result.account == campaign_account_a


def test_runtime_not_ready_and_all_unavailable(db_session) -> None:
    campaign, target = _campaign(db_session)
    _account, campaign_account = _add_account(db_session, campaign, "+15550104005", 1)

    result = AccountSelector(readiness_provider=FakeReadiness(set())).select_account(
        campaign, [campaign_account], target
    )

    assert result.account is None
    assert result.reason == "no_eligible_account"
    assert result.skipped[0].reason == "runtime_not_ready"


def test_default_readiness_skips_unusable_runtime_state(db_session) -> None:
    campaign, target = _campaign(db_session)
    broken = seed_account(
        db_session,
        external_ref="+15550104009",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="broken",
        session_present=True,
    )
    missing_session = seed_account(
        db_session,
        external_ref="+15550104010",
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=False,
    )
    broken_campaign_account = CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=broken.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    missing_session_campaign_account = CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=missing_session.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()

    result = AccountSelector(session=db_session).select_account(
        campaign,
        [broken_campaign_account, missing_session_campaign_account],
        target,
    )

    assert result.account is None
    assert [skip.reason for skip in result.skipped] == [
        "runtime_not_ready",
        "runtime_not_ready",
    ]


def test_rotation_handles_aware_last_used_and_never_used_accounts(db_session) -> None:
    campaign, target = _campaign(db_session, strategy="least_used")
    account_a, campaign_account_a = _add_account(db_session, campaign, "+15550104011", 1)
    account_b, campaign_account_b = _add_account(db_session, campaign, "+15550104012", 1)
    campaign_account_a.last_used_at = datetime(2026, 5, 19, tzinfo=UTC)
    campaign_account_b.last_used_at = None
    db_session.commit()

    least_used = AccountSelector(
        readiness_provider=FakeReadiness({account_a.id, account_b.id})
    ).select_account(campaign, [campaign_account_a, campaign_account_b], target)
    campaign.rotation_strategy = "round_robin"
    round_robin = AccountSelector(
        readiness_provider=FakeReadiness({account_a.id, account_b.id})
    ).select_account(campaign, [campaign_account_a, campaign_account_b], target)

    assert least_used.account == campaign_account_b
    assert round_robin.account == campaign_account_b


def test_selector_rate_limited_denied_and_blacklisted_targets(db_session) -> None:
    campaign, target = _campaign(db_session)
    account, campaign_account = _add_account(db_session, campaign, "+15550104007", 1)
    rate_limited = AccountSelector(
        session=db_session,
        readiness_provider=FakeReadiness({account.id}),
        limiter=DenyRateLimiter(),
    ).select_account(campaign, [campaign_account], target)
    ChannelRulesService().create_rule(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"target_ref": target.channel_ref, "rule_type": "blacklist"},
    )
    db_session.commit()
    blacklisted = AccountSelector(
        session=db_session,
        readiness_provider=FakeReadiness({account.id}),
    ).select_account(campaign, [campaign_account], target)

    assert rate_limited.account is None
    assert rate_limited.skipped[0].reason == "rate_limited"
    assert blacklisted.account is None
    assert blacklisted.skipped[0].reason == "blacklisted_for_target"


def test_selector_skips_foreign_workspace_account(db_session) -> None:
    _own, foreign_workspace = seed_two_workspaces(db_session)
    campaign, target = _campaign(db_session)
    foreign_account = seed_account(
        db_session,
        external_ref="+15550104008",
        workspace_id=foreign_workspace,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    campaign_account = NeuroCommentCampaignAccount(
        id=new_id(),
        campaign_id=campaign.id,
        account_id=foreign_account.id,
        status="active",
    )
    db_session.add(campaign_account)
    db_session.commit()

    result = AccountSelector(
        session=db_session, readiness_provider=FakeReadiness({foreign_account.id})
    ).select_account(campaign, [campaign_account], target)

    assert result.account is None
    assert result.skipped[0].reason == "workspace_mismatch"


def test_account_health_updates_counters_and_workspace_isolation(db_session) -> None:
    _own, foreign_workspace = seed_two_workspaces(db_session)
    campaign, _target = _campaign(db_session)
    _account, campaign_account = _add_account(db_session, campaign, "+15550104006", 1)
    foreign = CampaignService().create_campaign(
        db_session,
        workspace_id=foreign_workspace,
        actor_user_id="foreign",
        payload={"name": "foreign"},
    )
    db_session.commit()

    service = AccountHealthService()
    service.record_account_send_success(
        db_session,
        campaign_id=campaign.id,
        account_id=campaign_account.account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    service.record_account_send_failure(
        db_session,
        campaign_id=campaign.id,
        account_id=campaign_account.account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        error_code="SEND_FAILED",
    )
    service.record_account_flood_wait(
        db_session,
        campaign_id=campaign.id,
        account_id=campaign_account.account_id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        flood_wait_seconds=60,
    )

    assert campaign_account.comments_sent == 1
    assert campaign_account.comments_failed == 1
    assert campaign_account.status == "cooldown"
    assert campaign_account.last_error_code == "FLOOD_WAIT"
    try:
        service.record_account_send_success(
            db_session,
            campaign_id=foreign.id,
            account_id=campaign_account.account_id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        )
    except ValueError as exc:
        assert str(exc) == "campaign not found"
    else:
        raise AssertionError("foreign campaign was updated")
