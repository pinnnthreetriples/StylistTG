from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import Account
from app.modules.account_core.capabilities import build_account_capabilities as _build_capabilities
from app.modules.account_core.service import get_account, list_accounts


def lookup_account(
    session: Session, account_id: str, *, workspace_id: str | None = None
) -> Account | None:
    """Resolve an account within an optional workspace boundary."""
    return get_account(session, account_id, workspace_id=workspace_id)


def list_workspace_accounts(session: Session, *, workspace_id: str) -> list[Account]:
    """List accounts scoped to a workspace boundary."""
    return list_accounts(session, workspace_id=workspace_id)


def build_account_capabilities(
    account: Account,
    reasons: list[dict[str, Any]],
    *,
    config: Settings = settings,
    checked_at: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    """Build capability read model for cross-module account consumers."""
    return _build_capabilities(account, reasons, config=config, checked_at=checked_at)


__all__ = ["build_account_capabilities", "list_workspace_accounts", "lookup_account"]
