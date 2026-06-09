"""Public facade for `account_shared`.

Cross-module consumers (`account_safety`, `account_proxy`, `story`,
`bought_onboarding`, `account_ggr`, `account_editing`,
`account_lifecycle`, `account_profile_state`, etc.) import from this
module instead of from `account_core` directly so that the
account_core <-> {account_safety, warmup} cycles do not re-form, and
so that the cross-module-import architecture guard only sees an
allowlisted `interfaces` public submodule.

Runtime composition helpers (`refresh_account_runtime`,
`get_runtime_diagnostics`) live in `app.modules.account_shared.runtime`
and are exposed through this facade via a module-level `__getattr__`
hook. The lazy hook is required because the runtime helpers pull in
TDLib/profile adapters whose own initialisation transitively imports
`account_proxy.accounts`, which in turn imports this facade. Eagerly
importing `runtime` at facade load time would form an import-time cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.modules.account_shared.accounts import (
    list_workspace_accounts,
    lookup_account,
)
from app.modules.account_shared.capabilities import (
    CAPABILITY_KEYS,
    build_account_capabilities,
)
from app.modules.account_shared.readiness_risk import (
    build_account_readiness_risk,
    build_account_readiness_risk_summary,
)

if TYPE_CHECKING:  # pragma: no cover - import for type checkers only
    from app.modules.account_shared.runtime import (  # noqa: F401
        get_runtime_diagnostics,
        refresh_account_runtime,
    )


_LAZY_RUNTIME_EXPORTS = frozenset({"get_runtime_diagnostics", "refresh_account_runtime"})


def __getattr__(name: str) -> Any:
    if name in _LAZY_RUNTIME_EXPORTS:
        from app.modules.account_shared import runtime as _runtime

        return getattr(_runtime, name)
    raise AttributeError(
        f"module 'app.modules.account_shared.interfaces' has no attribute {name!r}"
    )


__all__ = [
    "CAPABILITY_KEYS",
    "build_account_readiness_risk",
    "build_account_readiness_risk_summary",
    "build_account_capabilities",
    "get_runtime_diagnostics",
    "list_workspace_accounts",
    "lookup_account",
    "refresh_account_runtime",
]
