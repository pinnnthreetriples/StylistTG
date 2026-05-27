from __future__ import annotations

import importlib

from app.modules.account_safety import contracts, interfaces, service
from app.modules.registry import iter_modules
from app.services import account_safety, account_safety_gate, safety_gate_reserve

EXPECTED_ACCOUNT_SAFETY_INTERFACE_SYMBOLS = [
    "SafetyGateReservation",
    "SafetyGateVerdict",
    "build_account_safety_for_account",
    "evaluate",
    "release",
    "reserve",
    "safety_preview_fields_with_policy",
    "unique_preserve_order",
]

FORBIDDEN_ACCOUNT_SAFETY_INTERFACE_SYMBOLS = {
    "AccountSafetyGate",
    "InMemorySafetyGateCache",
    "NullSafetyGateCache",
    "RedisSafetyGateCache",
    "SafetyGateCache",
    "WorkspaceSafetyPolicyDefaults",
    "apply_preset_defaults",
    "batch_active_overrides_by_operation",
    "compute_diff",
    "create_safety_override",
    "create_workspace_safety_policy",
    "delete_workspace_safety_policy",
    "get_redis_client",
    "get_workspace_safety_policy",
    "policy_public_snapshot",
    "redis_from_url",
    "update_workspace_safety_policy",
}


def test_account_safety_module_is_registered_as_public_boundary() -> None:
    module = next(module for module in iter_modules() if module.name == "account_safety")

    assert module.router_path == "app.modules.account_safety.router:router"
    assert module.workflows == ()


def test_account_safety_facade_preserves_existing_service_contracts() -> None:
    assert service.evaluate is account_safety_gate.evaluate
    assert service.build_account_safety is account_safety.build_account_safety
    assert service.reserve is safety_gate_reserve.reserve
    assert service.release is safety_gate_reserve.release


def test_account_safety_contracts_reexport_gate_and_read_models() -> None:
    assert contracts.SafetyGateVerdict.__name__ == "SafetyGateVerdict"
    assert contracts.AccountSafetyRead.__name__ == "AccountSafetyRead"


def test_account_safety_interfaces_exports_are_exact_public_boundary() -> None:
    assert interfaces.__all__ == EXPECTED_ACCOUNT_SAFETY_INTERFACE_SYMBOLS


def test_account_safety_interfaces_public_attrs_match_export_contract() -> None:
    public_attrs = sorted(
        name
        for name in vars(interfaces)
        if not name.startswith("_") and name not in {"annotations"}
    )

    assert public_attrs == sorted(EXPECTED_ACCOUNT_SAFETY_INTERFACE_SYMBOLS)
    assert set(interfaces._PUBLIC_SYMBOL_RATIONALE) == set(interfaces.__all__)
    assert all(len(rationale) >= 20 for rationale in interfaces._PUBLIC_SYMBOL_RATIONALE.values())
    assert FORBIDDEN_ACCOUNT_SAFETY_INTERFACE_SYMBOLS.isdisjoint(public_attrs)


def test_account_safety_legacy_wrappers_alias_canonical_modules() -> None:
    aliases = {
        "app.api.account_safety_routes": "app.modules.account_safety.accounts_router",
        "app.api.safety_policy": "app.modules.account_safety.policy_router",
        "app.contracts.safety": "app.modules.account_safety.read_contracts",
        "app.contracts.safety_gate": "app.modules.account_safety.gate_contracts",
        "app.services.account_batch_safety": "app.modules.account_safety.batch_preview",
        "app.services.account_safety": "app.modules.account_safety.read_models",
        "app.services.account_safety_gate": "app.modules.account_safety.gate",
        "app.services.account_safety_overrides": "app.modules.account_safety.overrides",
        "app.services.risk_gate": "app.modules.account_safety.action_gate",
        "app.services.safety_gate_cache": "app.modules.account_safety.cache",
        "app.services.safety_gate_reserve": "app.modules.account_safety.reserve",
        "app.services.workspace_safety_policy": "app.modules.account_safety.policy",
    }

    assert {
        legacy: importlib.import_module(legacy) is importlib.import_module(canonical)
        for legacy, canonical in aliases.items()
    } == dict.fromkeys(aliases, True)
