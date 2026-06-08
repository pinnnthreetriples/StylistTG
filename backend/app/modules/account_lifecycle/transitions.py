from __future__ import annotations

from enum import StrEnum


class AccountLifecycleState(StrEnum):
    IMPORTED = "imported"
    COLD_SOAK = "cold_soak"
    WARMING = "warming"
    PRE_PRODUCTION = "pre_production"
    ACTIVE = "active"
    IDLE = "idle"
    RETIRED = "retired"
    BANNED = "banned"
    DELETED = "deleted"


ALLOWED_TRANSITIONS: dict[AccountLifecycleState, frozenset[AccountLifecycleState]] = {
    AccountLifecycleState.IMPORTED: frozenset({AccountLifecycleState.COLD_SOAK}),
    AccountLifecycleState.COLD_SOAK: frozenset(
        {
            AccountLifecycleState.WARMING,
            AccountLifecycleState.RETIRED,
            AccountLifecycleState.BANNED,
            AccountLifecycleState.DELETED,
        }
    ),
    AccountLifecycleState.WARMING: frozenset(
        {AccountLifecycleState.PRE_PRODUCTION, AccountLifecycleState.COLD_SOAK}
    ),
    AccountLifecycleState.PRE_PRODUCTION: frozenset(
        {AccountLifecycleState.ACTIVE, AccountLifecycleState.COLD_SOAK}
    ),
    AccountLifecycleState.ACTIVE: frozenset(
        {AccountLifecycleState.IDLE, AccountLifecycleState.COLD_SOAK, AccountLifecycleState.RETIRED}
    ),
    AccountLifecycleState.IDLE: frozenset(
        {AccountLifecycleState.ACTIVE, AccountLifecycleState.RETIRED}
    ),
    AccountLifecycleState.RETIRED: frozenset(),
    AccountLifecycleState.BANNED: frozenset(),
    AccountLifecycleState.DELETED: frozenset(),
}

MANUAL_ONLY_DESTINATIONS = frozenset(
    {
        AccountLifecycleState.RETIRED,
        AccountLifecycleState.BANNED,
        AccountLifecycleState.DELETED,
    }
)
MANUAL_ONLY_TRANSITIONS = frozenset(
    {(AccountLifecycleState.WARMING, AccountLifecycleState.COLD_SOAK)}
)


def normalize_state(value: AccountLifecycleState | str) -> AccountLifecycleState:
    return value if isinstance(value, AccountLifecycleState) else AccountLifecycleState(value)


def is_transition_allowed(
    from_state: AccountLifecycleState | str,
    to_state: AccountLifecycleState | str,
    *,
    manual: bool = False,
) -> bool:
    source = normalize_state(from_state)
    target = normalize_state(to_state)
    if target not in ALLOWED_TRANSITIONS[source]:
        return False
    if not manual and target in MANUAL_ONLY_DESTINATIONS:
        return False
    return manual or (source, target) not in MANUAL_ONLY_TRANSITIONS


__all__ = [
    "ALLOWED_TRANSITIONS",
    "AccountLifecycleState",
    "is_transition_allowed",
    "normalize_state",
]
