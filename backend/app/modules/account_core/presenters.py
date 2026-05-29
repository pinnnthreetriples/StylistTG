from __future__ import annotations

from typing import Any, Literal, cast

from app.models import Account
from app.schemas import (
    AccountListItemRead,
    AccountWarmupInfoRead,
    TerminalStatus,
)

AccountOrigin = Literal["imported", "bought", "created"]


def account_list_item_batched(
    account: Account,
    warmup_map: dict[str, Any],
    photo_map: dict[str, str | None],
) -> AccountListItemRead:
    profile = account.profile_state
    first_name = profile.first_name if profile else None
    last_name = profile.last_name if profile else None
    display_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    username = profile.username if profile else None
    runtime = account.runtime_state
    warmup_session = warmup_map.get(account.id)
    locked_operations = {"profile_update", "proxy_change", "account_delete"}
    is_locked = warmup_session is not None and "profile_update" in locked_operations
    warmup_info: AccountWarmupInfoRead | None = None
    if warmup_session is not None:
        warmup_info = AccountWarmupInfoRead(
            session_id=warmup_session.id,  # type: ignore[union-attr]
            status=warmup_session.status,  # type: ignore[union-attr]
            current_day=warmup_session.current_day,  # type: ignore[union-attr]
            is_locked=is_locked,
        )
    return AccountListItemRead(
        account_id=account.id,
        display_name=display_name,
        username=username,
        phone_number=account.external_ref,
        telegram_user_id=account.telegram_user_id,
        origin=_account_origin(account),
        account_state=account.account_state,
        terminal_status=_terminal_status(account),
        runtime_health=runtime.runtime_health,
        is_execution_usable=account.account_state == "execution_usable",
        is_test_dc=_is_test_dc_account(account),
        profile_photo_asset_id=photo_map.get(account.id),
        updated_at=account.updated_at,
        warmup=warmup_info,
    )


def _is_test_dc_account(account: Account) -> bool:
    return account.external_ref.startswith("+999") or account.telegram_user_id == "mock-user"


def _account_origin(account: Account) -> AccountOrigin:
    return cast(AccountOrigin, account.origin)


def _terminal_status(account: Account) -> TerminalStatus:
    return cast(TerminalStatus, account.terminal_status)


__all__ = [
    "AccountOrigin",
    "account_list_item_batched",
]
