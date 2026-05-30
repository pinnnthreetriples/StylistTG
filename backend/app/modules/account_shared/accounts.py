"""Account lookup primitives shared across feature modules.

These helpers query the `Account` model directly so that `account_shared`
stays a neutral leaf — i.e. it does not import from `account_core`,
`account_safety`, or `warmup`. Owning these primitives here is what
breaks the historical account_core <-> account_safety / warmup cycles.

`account_core.service` still owns CRUD for accounts; these are the
narrow read primitives other feature modules need.
"""

from __future__ import annotations

from sqlalchemy import not_, select
from sqlalchemy.orm import Session, joinedload

from app.models import DEFAULT_LOCAL_WORKSPACE_ID, Account, AccountState


def lookup_account(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Account | None:
    """Resolve an account within an optional workspace boundary."""
    if workspace_id is None:
        return session.get(Account, account_id)
    return (
        session.execute(
            select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )


def list_workspace_accounts(
    session: Session, *, workspace_id: str = DEFAULT_LOCAL_WORKSPACE_ID
) -> list[Account]:
    """List accounts scoped to a workspace boundary.

    Matches the read shape used by `account_core.service.list_accounts`:
    eager-loads profile/runtime/proxy, filters out half-authenticated
    batch rows, and orders by recency.
    """
    return list(
        session.execute(
            select(Account)
            .options(
                joinedload(Account.profile_state),
                joinedload(Account.runtime_state),
                joinedload(Account.proxy),
            )
            .where(Account.workspace_id == workspace_id)
            .where(
                not_(
                    (Account.auth_source == "batch")
                    & Account.account_state.in_(
                        [
                            AccountState.REGISTERED,
                            AccountState.AUTH_PENDING,
                            AccountState.AWAITING_CODE,
                            AccountState.AWAITING_PASSWORD,
                        ]
                    )
                )
            )
            .order_by(Account.updated_at.desc())
        )
        .unique()
        .scalars()
        .all()
    )


__all__ = ["list_workspace_accounts", "lookup_account"]
