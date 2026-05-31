from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ACTIVE_WARMUP_STATUSES,
    Account,
    AccountProxy,
    AccountState,
    WarmupSession,
    WarmupStrategy,
)
from app.modules.warmup.contracts import (
    WarmupCheckItemRead,
    WarmupCheckSeverityRead,
    WarmupValidateRead,
)


def validate_warmup_readiness(
    session: Session,
    *,
    account_id: str,
    strategy_id: str,
    workspace_id: str,
) -> WarmupValidateRead:
    checks: list[WarmupCheckItemRead] = []

    account = _load_account(session, account_id=account_id, workspace_id=workspace_id)
    checks.append(_account_exists_check(account))

    strategy = _load_strategy(session, strategy_id=strategy_id, workspace_id=workspace_id)
    checks.append(_strategy_exists_check(strategy))
    checks.append(_runtime_ready_check(account))
    checks.append(
        _active_session_check(session, account=account, account_id=account_id, workspace_id=workspace_id)
    )

    if account is not None:
        checks.append(_proxy_status_check(session, account))

    blocking_reasons = _failed_check_messages(checks, WarmupCheckSeverityRead.ERROR)
    warnings = _failed_check_messages(checks, WarmupCheckSeverityRead.WARNING)
    return WarmupValidateRead(
        is_ready=not blocking_reasons,
        checks=checks,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
    )


def _load_account(session: Session, *, account_id: str, workspace_id: str) -> Account | None:
    return (
        session.execute(
            select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )


def _load_strategy(
    session: Session, *, strategy_id: str, workspace_id: str
) -> WarmupStrategy | None:
    return (
        session.execute(
            select(WarmupStrategy).where(
                WarmupStrategy.id == strategy_id,
                (WarmupStrategy.workspace_id == workspace_id)
                | (WarmupStrategy.workspace_id.is_(None)),
            )
        )
        .scalars()
        .first()
    )


def _account_exists_check(account: Account | None) -> WarmupCheckItemRead:
    return _check(
        key="account_exists",
        label="Аккаунт найден",
        passed=account is not None,
        detail=None if account is not None else "Аккаунт не найден в текущем рабочем пространстве",
    )


def _strategy_exists_check(strategy: WarmupStrategy | None) -> WarmupCheckItemRead:
    return _check(
        key="strategy_exists",
        label="Стратегия найдена",
        passed=strategy is not None,
        detail=None if strategy is not None else "Стратегия подготовки не найдена",
    )


def _runtime_ready_check(account: Account | None) -> WarmupCheckItemRead:
    runtime_state = cast(Any, account.runtime_state) if account is not None else None
    runtime_ready = bool(
        account is not None
        and runtime_state is not None
        and runtime_state.session_present
        and not runtime_state.reauth_required
        and runtime_state.runtime_health == "ready"
        and account.account_state == AccountState.EXECUTION_USABLE
    )
    return _check(
        key="runtime_ready",
        label="Аккаунт готов к выполнению",
        passed=runtime_ready,
        detail=None if runtime_ready else "Аккаунт не готов: требуется авторизация или проверка runtime",
    )


def _active_session_check(
    session: Session,
    *,
    account: Account | None,
    account_id: str,
    workspace_id: str,
) -> WarmupCheckItemRead:
    has_active_session = bool(
        account is not None
        and session.execute(
            select(WarmupSession.id).where(
                WarmupSession.workspace_id == workspace_id,
                WarmupSession.account_id == account_id,
                WarmupSession.status.in_([s.value for s in ACTIVE_WARMUP_STATUSES]),
            )
        ).first()
        is not None
    )
    return _check(
        key="no_active_session",
        label="Нет активной подготовки",
        passed=not has_active_session,
        detail="Для аккаунта уже есть активная подготовка" if has_active_session else None,
    )


def _proxy_status_check(session: Session, account: Account) -> WarmupCheckItemRead:
    proxy = session.get(AccountProxy, account.id)
    proxy_ok = proxy is None or proxy.status in {"unknown", "tcp_working", "tdlib_working"}
    proxy_status = proxy.status if proxy is not None else None
    return _check(
        key="proxy_status",
        label="Proxy без критичных диагностических ошибок",
        passed=proxy_ok,
        severity=WarmupCheckSeverityRead.WARNING,
        detail=None if proxy_ok else f"Proxy требует внимания: {proxy_status}",
    )


def _failed_check_messages(
    checks: list[WarmupCheckItemRead], severity: WarmupCheckSeverityRead
) -> list[str]:
    return [item.detail or item.label for item in checks if item.severity == severity and not item.passed]


def _check(
    *,
    key: str,
    label: str,
    passed: bool,
    severity: WarmupCheckSeverityRead = WarmupCheckSeverityRead.ERROR,
    detail: str | None = None,
) -> WarmupCheckItemRead:
    return WarmupCheckItemRead(
        key=key,
        label=label,
        passed=passed,
        severity=severity,
        detail=detail,
    )
