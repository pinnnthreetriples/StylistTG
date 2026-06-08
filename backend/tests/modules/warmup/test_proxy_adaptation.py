from __future__ import annotations

from app.modules.warmup.action_metadata import TRAFFIC_HEAVY_ACTIONS
from app.modules.warmup.proxy_adaptation import (
    compute_disabled_actions_for_proxy,
    select_preset_by_proxy,
)


def test_select_preset_by_proxy_maps_known_categories() -> None:
    assert select_preset_by_proxy("datacenter") == "full"
    assert select_preset_by_proxy("residential") == "balanced"
    assert select_preset_by_proxy("mobile") == "economic"
    assert select_preset_by_proxy(None) == "balanced"


def test_compute_disabled_actions_for_proxy_disables_traffic_heavy_for_paid_proxy() -> None:
    assert set(compute_disabled_actions_for_proxy("mobile")) == set(TRAFFIC_HEAVY_ACTIONS)
    assert set(compute_disabled_actions_for_proxy("residential")) == set(TRAFFIC_HEAVY_ACTIONS)
    assert compute_disabled_actions_for_proxy("datacenter") == []
    assert compute_disabled_actions_for_proxy(None) == []
