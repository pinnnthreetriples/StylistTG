from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, AccountState
from app.services.neuro_commenting.campaign_account_service import CampaignAccountService
from app.services.neuro_commenting.campaign_service import (
    SAFETY_PRESET_LIMITS,
    CampaignService,
)
from tests.helpers.factories import seed_account


def _seed_account_with_age(db_session, *, hours_old: float, ref: str):
    account = seed_account(
        db_session,
        external_ref=ref,
        account_state=AccountState.EXECUTION_USABLE,
        runtime_health="ready",
        session_present=True,
    )
    account.created_at = datetime.now(UTC) - timedelta(hours=hours_old)
    db_session.flush()
    return account


def test_safety_preset_default_is_balanced(db_session) -> None:
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Default preset"},
    )
    db_session.commit()
    db_session.refresh(campaign)

    assert campaign.safety_preset == "balanced"


def test_safety_preset_invalid_value_rejected(db_session) -> None:
    with pytest.raises(ValueError, match="invalid safety_preset"):
        CampaignService().create_campaign(
            db_session,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            actor_user_id="user-1",
            payload={"name": "Invalid", "safety_preset": "extreme"},
        )


def test_safety_preset_limits_table_has_conservative_balanced_aggressive() -> None:
    assert set(SAFETY_PRESET_LIMITS.keys()) == {"conservative", "balanced", "aggressive"}
    assert SAFETY_PRESET_LIMITS["conservative"].per_hour < SAFETY_PRESET_LIMITS["balanced"].per_hour
    assert SAFETY_PRESET_LIMITS["balanced"].per_hour < SAFETY_PRESET_LIMITS["aggressive"].per_hour
    assert (
        SAFETY_PRESET_LIMITS["conservative"].min_delay_seconds
        > SAFETY_PRESET_LIMITS["aggressive"].min_delay_seconds
    )


def test_start_campaign_blocks_aggressive_preset_for_fresh_account(db_session) -> None:
    account = _seed_account_with_age(db_session, hours_old=24, ref="+15550108001")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Aggressive fresh", "safety_preset": "aggressive"},
    )
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="age_forces_conservative"):
        CampaignService().start_campaign(
            db_session,
            campaign_id=campaign.id,
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            actor_user_id="user-1",
        )


def test_start_campaign_allows_conservative_preset_for_fresh_account(db_session) -> None:
    account = _seed_account_with_age(db_session, hours_old=24, ref="+15550108002")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Conservative fresh", "safety_preset": "conservative"},
    )
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()

    started = CampaignService().start_campaign(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    assert started.status == "running"


def test_start_campaign_allows_aggressive_preset_for_old_account(db_session) -> None:
    account = _seed_account_with_age(db_session, hours_old=24 * 40, ref="+15550108003")
    campaign = CampaignService().create_campaign(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
        payload={"name": "Aggressive aged", "safety_preset": "aggressive"},
    )
    CampaignAccountService().add_account(
        db_session,
        campaign_id=campaign.id,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    db_session.commit()

    started = CampaignService().start_campaign(
        db_session,
        campaign_id=campaign.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id="user-1",
    )
    assert started.status == "running"
