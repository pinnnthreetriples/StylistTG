from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.models import Account, AccountRuntimeState, AccountState, utc_now
from app.services.accounts import get_account


class ExecutionUsableAdapter(Protocol):
    def inspect_runtime(self, account_id: str) -> dict: ...


@dataclass(frozen=True)
class ExecutionUsableResult:
    account: Account
    runtime_state: AccountRuntimeState
    ok: bool
    error: str | None = None


def ensure_execution_usable(
    session: Session,
    account_id: str,
    *,
    adapter: ExecutionUsableAdapter,
) -> ExecutionUsableResult:
    account = get_account(session, account_id)
    if account is None:
        raise ValueError("account not found")

    inspection = adapter.inspect_runtime(account_id)
    account.account_state = inspection["account_state"]
    if inspection.get("telegram_user_id"):
        account.telegram_user_id = inspection["telegram_user_id"]

    runtime = account.runtime_state
    runtime.runtime_health = inspection["runtime_health"]
    runtime.reauth_required = inspection["account_state"] == AccountState.REAUTH_REQUIRED
    runtime.updated_at = utc_now()
    if inspection.get("ok"):
        runtime.session_present = True
        runtime.authorized_last_confirmed_at = utc_now()
    else:
        runtime.session_present = False
    runtime.recovery_marker = f"execution_policy:{inspection['runtime_health']}"

    session.commit()
    session.refresh(account)
    session.refresh(runtime)
    return ExecutionUsableResult(
        account=account,
        runtime_state=runtime,
        ok=bool(inspection["ok"]),
        error=inspection.get("error"),
    )
