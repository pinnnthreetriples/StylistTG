from __future__ import annotations

from typing import Any, Literal

from sqlalchemy.orm import Session

from app.modules.account_shared.interfaces import list_workspace_accounts
from app.modules.warmup.contracts import WarmupSelectableAccountRead
from app.modules.warmup.service import batch_active_warmups_for_accounts

OK_PROXY_STATUSES = {"ok", "ready", "active", "verified"}


def list_selectable_accounts(
    session: Session,
    *,
    workspace_id: str,
    search: str | None = None,
    country: str | None = None,
    role: str | None = None,
    proxy_ok_only: bool = False,
    hide_in_work: bool = False,
    limit: int = 500,
) -> list[WarmupSelectableAccountRead]:
    accounts = list_workspace_accounts(session, workspace_id=workspace_id)
    warmup_map = batch_active_warmups_for_accounts(
        session,
        account_ids=[account.id for account in accounts],
        workspace_id=workspace_id,
    )
    rows = [_to_selectable_account(account, warmup_map) for account in accounts]
    rows = _apply_filters(
        rows,
        search=search,
        country=country,
        role=role,
        proxy_ok_only=proxy_ok_only,
        hide_in_work=hide_in_work,
    )
    return rows[: max(1, min(limit, 500))]


def _to_selectable_account(account: Any, warmup_map: dict[str, Any]) -> WarmupSelectableAccountRead:
    profile = account.profile_state
    first_name = profile.first_name if profile else None
    last_name = profile.last_name if profile else None
    display_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    country = _country_from_phone(account.external_ref)
    warmup = warmup_map.get(account.id)
    proxy = account.proxy
    tags = [str(account.origin), str(account.runtime_state.runtime_health)]
    if proxy is not None:
        tags.append(str(proxy.proxy_category))
    return WarmupSelectableAccountRead(
        account_id=account.id,
        display_name=display_name,
        username=profile.username if profile else None,
        phone_number=account.external_ref,
        role=str(account.origin),
        country=country,
        country_iso=country,
        validity_badge=_validity_badge(account),
        proxy_badge=_proxy_badge(proxy),
        phase_badge="warming" if warmup is not None else "new",
        tags=tags,
        is_in_work=warmup is not None,
    )


def _apply_filters(
    rows: list[WarmupSelectableAccountRead],
    *,
    search: str | None,
    country: str | None,
    role: str | None,
    proxy_ok_only: bool,
    hide_in_work: bool,
) -> list[WarmupSelectableAccountRead]:
    needle = (search or "").strip().casefold()
    country_filter = (country or "").strip().upper()
    role_filter = (role or "").strip().casefold()
    filtered = rows
    if needle:
        filtered = [
            row
            for row in filtered
            if needle in row.account_id.casefold()
            or needle in row.phone_number.casefold()
            or needle in (row.username or "").casefold()
        ]
    if country_filter:
        filtered = [row for row in filtered if row.country_iso == country_filter]
    if role_filter:
        filtered = [row for row in filtered if row.role.casefold() == role_filter]
    if proxy_ok_only:
        filtered = [row for row in filtered if row.proxy_badge == "ok"]
    if hide_in_work:
        filtered = [row for row in filtered if not row.is_in_work]
    return filtered


def _validity_badge(account: Any) -> Literal["valid", "needs_login", "blocked", "unknown"]:
    if account.terminal_status != "none":
        return "blocked"
    if account.account_state == "execution_usable":
        return "valid"
    if getattr(account.runtime_state, "reauth_required", False):
        return "needs_login"
    return "unknown"


def _proxy_badge(proxy: Any | None) -> Literal["ok", "issue", "missing", "unknown"]:
    if proxy is None:
        return "missing"
    status = str(proxy.status or "unknown").strip().lower()
    if status in OK_PROXY_STATUSES or proxy.tdlib_verified_at is not None:
        return "ok"
    if status in {"failed", "error", "blocked"} or proxy.last_error_code:
        return "issue"
    return "unknown"


def _country_from_phone(phone: str) -> str:
    normalized = "".join(char for char in phone if char.isdigit() or char == "+")
    for prefix, country in (
        ("+57", "CO"),
        ("+380", "UA"),
        ("+44", "GB"),
        ("+49", "DE"),
        ("+7", "RU"),
        ("+1", "CA"),
    ):
        if normalized.startswith(prefix):
            return country
    return "XX"
