"""Phase 2/3/4 warmup TDLib adapter facade."""

from __future__ import annotations

from app.adapters.tdlib_auth import RealTdJsonClientFactory, TdlibClientFactory
from app.adapters.warmup_tdlib_contracts import (
    SUPPORTED_ACTIONS_BY_MODE,
    SUPPORTED_ADVANCED_ACTIONS,
    SUPPORTED_NETWORK_ACTIONS,
    SUPPORTED_PASSIVE_ACTIONS,
    WRITE_ACTION_TYPES,
    WarmupActionResult,
    WarmupTdlibAdapter,
    collect_supported_actions,
)
from app.adapters.warmup_tdlib_errors import _AdapterClientError, _classify_tdlib_error
from app.adapters.warmup_tdlib_mock import MockWarmupTdlibAdapter, UnavailableWarmupTdlibAdapter
from app.adapters.warmup_tdlib_real import RealWarmupTdlibAdapter
from app.config import Settings, settings


def build_warmup_tdlib_adapter(config: Settings = settings) -> WarmupTdlibAdapter:
    active_modes: list[str] = []
    if config.warmup_passive_enabled:
        active_modes.append("passive")
    if config.warmup_network_enabled:
        active_modes.append("network")
    if config.warmup_advanced_enabled:
        active_modes.append("advanced")
    if not active_modes:
        return UnavailableWarmupTdlibAdapter("warmup_live_levels_all_disabled")
    try:
        factory: TdlibClientFactory = RealTdJsonClientFactory(config.tdlib_shared_library_path)
    except OSError as exc:
        return UnavailableWarmupTdlibAdapter(f"tdlib_load_failed: {exc}")
    return RealWarmupTdlibAdapter(
        client_factory=factory,
        config=config,
        supported_modes=tuple(active_modes),
    )


__all__ = [
    "SUPPORTED_ACTIONS_BY_MODE",
    "SUPPORTED_ADVANCED_ACTIONS",
    "SUPPORTED_NETWORK_ACTIONS",
    "SUPPORTED_PASSIVE_ACTIONS",
    "WRITE_ACTION_TYPES",
    "MockWarmupTdlibAdapter",
    "RealWarmupTdlibAdapter",
    "UnavailableWarmupTdlibAdapter",
    "WarmupActionResult",
    "WarmupTdlibAdapter",
    "_AdapterClientError",
    "_classify_tdlib_error",
    "build_warmup_tdlib_adapter",
    "collect_supported_actions",
]
