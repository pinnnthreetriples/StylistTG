from app.models import (
    AccountProxy,
    AccountRuntimeState,
    AccountState,
    DEFAULT_LOCAL_WORKSPACE_ID,
    WarmupSession,
    WarmupStatus,
    WarmupStrategy,
    new_id,
)
from app.services.accounts import create_account
from app.services.warmup_readiness import validate_warmup_readiness


def test_warmup_readiness_passes_for_execution_usable_account(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)

    result = validate_warmup_readiness(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert result.is_ready is True
    assert result.blocking_reasons == []
    assert _check(result, "account_exists").passed is True
    assert _check(result, "runtime_ready").passed is True
    assert _check(result, "no_active_session").passed is True


def test_warmup_readiness_blocks_when_active_session_exists(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    db_session.add(
        WarmupSession(
            id=new_id(),
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account.id,
            strategy_id=strategy.id,
            status=WarmupStatus.ACTIVE,
            current_day=3,
            cadence_hours=24,
        )
    )
    db_session.commit()

    result = validate_warmup_readiness(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert result.is_ready is False
    assert "Для аккаунта уже есть активная подготовка" in result.blocking_reasons
    assert _check(result, "no_active_session").passed is False


def test_warmup_readiness_treats_proxy_problem_as_warning_only(db_session) -> None:
    account = _seed_ready_account(db_session)
    strategy = _seed_strategy(db_session)
    db_session.add(
        AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            proxy_category="mobile",
            host="127.0.0.1",
            port=1080,
            status="failed",
            last_error_code="PROXY_FAILED",
        )
    )
    db_session.commit()

    result = validate_warmup_readiness(
        db_session,
        account_id=account.id,
        strategy_id=strategy.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )

    assert result.is_ready is True
    assert result.blocking_reasons == []
    assert "Proxy требует внимания: failed" in result.warnings
    assert _check(result, "proxy_status").severity == "warning"
    assert result.proxy_adaptation is not None
    assert result.proxy_adaptation.applied_preset == "economic"
    assert "watch_video" in result.proxy_adaptation.disabled_actions


def _seed_ready_account(db_session):
    account = create_account(
        db_session,
        external_ref=f"+7999{new_id()[:8]}",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
    )
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state = AccountRuntimeState(
        account_id=account.id,
        session_present=True,
        runtime_health="ready",
        reauth_required=False,
    )
    db_session.commit()
    return account


def _seed_strategy(db_session) -> WarmupStrategy:
    strategy = WarmupStrategy(
        id=new_id(),
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        name=f"Стратегия {new_id()[:8]}",
        description="Тестовая стратегия",
        tier_limits_json={},
        target_channels_json=[],
        is_preset=True,
    )
    db_session.add(strategy)
    db_session.commit()
    return strategy


def _check(result, key: str):
    return next(item for item in result.checks if item.key == key)
