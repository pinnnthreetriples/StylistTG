from __future__ import annotations

import importlib

from app.modules.account_safety import contracts, service
from app.modules.registry import iter_modules
from app.services import account_safety, account_safety_gate, safety_gate_reserve


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
