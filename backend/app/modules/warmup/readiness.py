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

    account = (
        session.execute(
            select(Account).where(Account.id == account_id, Account.workspace_id == workspace_id)
        )
        .scalars()
        .first()
    )
    checks.append(
        _check(
            key="account_exists",
            label="Аккаунт найден",
            passed=account is not None,
            detail=None
            if account is not None
            else "Аккаунт не найден в текущем рабочем пространстве",
        )
    )

    strategy = (
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
    checks.append(
        _check(
            key="strategy_exists",
            label="Стратегия найдена",
            passed=strategy is not None,
            detail=None if strategy is not None else "Стратегия подготовки не найдена",
        )
    )

    runtime_state = cast(Any, account.runtime_state) if account is not None else None
    runtime_ready = bool(
        account is not None
        and runtime_state is not None
        and runtime_state.session_present
        and not runtime_state.reauth_required
        and runtime_state.runtime_health == "ready"
        and account.account_state == AccountState.EXECUTION_USABLE
    )
    checks.append(
        _check(
            key="runtime_ready",
            label="Аккаунт готов к выполнению",
            passed=runtime_ready,
            detail=None
            if runtime_ready
            else "Аккаунт не готов: требуется авторизация или проверка runtime",
        )
    )

    has_active_session = False
    if account is not None:
        has_active_session = (
            session.execute(
                select(WarmupSession.id).where(
                    WarmupSession.workspace_id == workspace_id,
                    WarmupSession.account_id == account_id,
                    WarmupSession.status.in_([s.value for s in ACTIVE_WARMUP_STATUSES]),
                )
            ).first()
            is not None
        )
    checks.append(
        _check(
            key="no_active_session",
            label="Нет активной подготовки",
            passed=not has_active_session,
            detail="Для аккаунта уже есть активная подготовка" if has_active_session else None,
        )
    )

    if account is not None:
        proxy = session.get(AccountProxy, account.id)
        proxy_ok = proxy is None or proxy.status in {"unknown", "tcp_working", "tdlib_working"}
        proxy_status = proxy.status if proxy is not None else None
        checks.append(
            _check(
                key="proxy_status",
                label="Proxy без критичных диагностических ошибок",
                passed=proxy_ok,
                severity=WarmupCheckSeverityRead.WARNING,
                detail=None if proxy_ok else f"Proxy требует внимания: {proxy_status}",
            )
        )

    blocking_reasons = [
        item.detail or item.label
        for item in checks
        if item.severity == WarmupCheckSeverityRead.ERROR and not item.passed
    ]
    warnings = [
        item.detail or item.label
        for item in checks
        if item.severity == WarmupCheckSeverityRead.WARNING and not item.passed
    ]
    return WarmupValidateRead(
        is_ready=not blocking_reasons,
        checks=checks,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
    )


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
