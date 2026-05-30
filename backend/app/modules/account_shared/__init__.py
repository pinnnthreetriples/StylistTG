"""Neutral shared primitives for account feature modules.

Holds the small set of read-only/composition helpers other modules need
(account lookup/list, capabilities, runtime read facade, warmup status
composition). Owning these in a separate module breaks the otherwise
mutual dependencies between `account_core`, `account_safety`, and
`warmup`.
"""

from app.modules.account_shared.module import module

__all__ = ["module"]
