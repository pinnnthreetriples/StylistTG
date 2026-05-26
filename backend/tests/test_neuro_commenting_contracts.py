from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.contracts.neuro_commenting import (
    NeuroCampaignCreate,
    NeuroCampaignUpdate,
    NeuroChannelRuleCreate,
)


def test_campaign_create_accepts_supported_mode() -> None:
    campaign = NeuroCampaignCreate(name="Phase 0", mode="keyword_match")

    assert campaign.mode == "keyword_match"


def test_campaign_create_rejects_semantic_match_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        NeuroCampaignCreate(name="Phase 0", mode="semantic_match")

    assert "feature_not_available: mode=semantic_match" in str(exc_info.value)


def test_campaign_create_rejects_scheduled_work_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        NeuroCampaignCreate(name="Phase 0", work_mode="scheduled")

    assert "feature_not_available: work_mode=scheduled" in str(exc_info.value)


def test_campaign_update_rejects_semantic_match_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        NeuroCampaignUpdate(mode="semantic_match")

    assert "feature_not_available: mode=semantic_match" in str(exc_info.value)


def test_campaign_update_rejects_scheduled_work_mode() -> None:
    with pytest.raises(ValidationError) as exc_info:
        NeuroCampaignUpdate(work_mode="scheduled")

    assert "feature_not_available: work_mode=scheduled" in str(exc_info.value)


def test_campaign_update_allows_none_for_disabled_fields() -> None:
    payload = NeuroCampaignUpdate(mode=None, work_mode=None, name="rename")

    assert payload.mode is None
    assert payload.work_mode is None
    assert payload.name == "rename"


def test_channel_rule_create_accepts_blacklist() -> None:
    rule = NeuroChannelRuleCreate(target_ref="@example", rule_type="blacklist")

    assert rule.rule_type == "blacklist"


def test_channel_rule_create_rejects_auto_blacklist_suggested_outside_create_enum() -> None:
    with pytest.raises(ValidationError) as exc_info:
        NeuroChannelRuleCreate(target_ref="@example", rule_type="auto_blacklist_suggested")

    assert "Input should be 'blacklist' or 'whitelist'" in str(exc_info.value)


def test_channel_rule_create_rejects_auto_whitelist_suggested_outside_create_enum() -> None:
    with pytest.raises(ValidationError) as exc_info:
        NeuroChannelRuleCreate(target_ref="@example", rule_type="auto_whitelist_suggested")

    assert "Input should be 'blacklist' or 'whitelist'" in str(exc_info.value)
