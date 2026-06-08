from app.models import DEFAULT_LOCAL_WORKSPACE_ID, WarmupStrategy
from app.modules.warmup.idle_session import IDLE_KEEPALIVE_STRATEGY_NAME
from app.scripts.seed_warmup_strategies import seed_warmup_strategies


def test_seed_warmup_strategies_is_idempotent(db_session) -> None:
    first_count = seed_warmup_strategies(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)
    second_count = seed_warmup_strategies(db_session, workspace_id=DEFAULT_LOCAL_WORKSPACE_ID)

    strategies = db_session.query(WarmupStrategy).all()
    assert first_count == 4
    assert second_count == 0
    assert len(strategies) == 4
    assert {strategy.name for strategy in strategies} == {
        IDLE_KEEPALIVE_STRATEGY_NAME,
        "Мягкая подготовка",
        "Стандартная подготовка",
        "Строгая подготовка",
    }
