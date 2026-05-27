from __future__ import annotations

from app.modules.account_safety import contracts, service
from app.modules.registry import iter_modules
from app.services import account_safety, account_safety_gate, safety_gate_reserve


def test_account_safety_module_is_registered_as_public_boundary() -> None:
    module = next(module for module in iter_modules() if module.name == "account_safety")

    assert module.router_path is None
    assert module.workflows == ()


def test_account_safety_facade_preserves_existing_service_contracts() -> None:
    assert service.evaluate is account_safety_gate.evaluate
    assert service.build_account_safety is account_safety.build_account_safety
    assert service.reserve is safety_gate_reserve.reserve
    assert service.release is safety_gate_reserve.release


def test_account_safety_contracts_reexport_gate_and_read_models() -> None:
    assert contracts.SafetyGateVerdict.__name__ == "SafetyGateVerdict"
    assert contracts.AccountSafetyRead.__name__ == "AccountSafetyRead"
