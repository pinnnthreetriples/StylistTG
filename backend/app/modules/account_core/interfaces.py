from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Account
from app.modules.account_core.service import get_account


def lookup_account(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Account | None:
    """Resolve an account within an optional workspace boundary."""
    return get_account(session, account_id, workspace_id=workspace_id)


__all__ = ["lookup_account"]
