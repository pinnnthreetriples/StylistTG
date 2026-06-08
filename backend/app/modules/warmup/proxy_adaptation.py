from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.adapters.warmup_tdlib_contracts import SUPPORTED_ADVANCED_ACTIONS
from app.modules.warmup.action_metadata import TRAFFIC_HEAVY_ACTIONS

ProxyAdaptivePreset = Literal["economic", "balanced", "full"]

PROXY_TO_PRESET: dict[str, ProxyAdaptivePreset] = {
    "datacenter": "full",
    "residential": "balanced",
    "mobile": "economic",
}


@dataclass(frozen=True)
class ProxyAdaptation:
    proxy_category: str
    applied_preset: ProxyAdaptivePreset
    disabled_actions: list[str]

    def as_payload(self) -> dict[str, object]:
        return {
            "proxy_category": self.proxy_category,
            "applied_preset": self.applied_preset,
            "disabled_actions": list(self.disabled_actions),
        }


def select_preset_by_proxy(proxy_category: str | None) -> ProxyAdaptivePreset:
    return PROXY_TO_PRESET.get(_normalize_proxy_category(proxy_category), "balanced")


def compute_disabled_actions_for_proxy(proxy_category: str | None) -> list[str]:
    category = _normalize_proxy_category(proxy_category)
    if category not in {"mobile", "residential"}:
        return []
    return [
        action_type
        for action_type in SUPPORTED_ADVANCED_ACTIONS
        if action_type in TRAFFIC_HEAVY_ACTIONS
    ]


def adaptation_for_proxy(proxy_category: str | None) -> ProxyAdaptation:
    category = _normalize_proxy_category(proxy_category)
    return ProxyAdaptation(
        proxy_category=category,
        applied_preset=select_preset_by_proxy(category),
        disabled_actions=compute_disabled_actions_for_proxy(category),
    )


def _normalize_proxy_category(proxy_category: str | None) -> str:
    value = (proxy_category or "unknown").strip().lower()
    return value or "unknown"


__all__ = [
    "PROXY_TO_PRESET",
    "ProxyAdaptation",
    "ProxyAdaptivePreset",
    "adaptation_for_proxy",
    "compute_disabled_actions_for_proxy",
    "select_preset_by_proxy",
]
