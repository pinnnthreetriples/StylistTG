from __future__ import annotations


def test_models_facade_exports_split_models_and_configures_mappers() -> None:
    from sqlalchemy.orm import configure_mappers

    from app.models import Account, AccountProxy, AuthBatch, RateLimitPersistentCounter, Workspace

    configure_mappers()

    assert Account.__tablename__ == "account"
    assert AccountProxy.__tablename__ == "account_proxy"
    assert AuthBatch.__tablename__ == "auth_batch"
    assert RateLimitPersistentCounter.__tablename__ == "rate_limit_persistent_counters"
    assert Workspace.__tablename__ == "workspace"


def test_schemas_facade_exports_split_schemas_and_lazy_account_editing_contracts() -> None:
    from app import schemas
    from app.schemas import AccountCreate, ProfileJobCreate, TelegramAuthSessionCreate

    assert AccountCreate(external_ref="account-1").external_ref == "account-1"
    assert TelegramAuthSessionCreate(phone_number="+10000000000").phone_number == "+10000000000"
    assert ProfileJobCreate(account_id="account-1").account_id == "account-1"
    assert schemas.AccountUpdateCreate.__name__ == "AccountUpdateCreate"


def test_legacy_facades_keep_public_import_contracts() -> None:
    from app.modules.neuro_commenting.rate_limiter import RATE_LIMIT_COUNTER_SCAN_PATTERN
    from app.services.account_safety_gate import AccountSafetyGate, InMemorySafetyGateCache

    assert AccountSafetyGate.__name__ == "AccountSafetyGate"
    assert InMemorySafetyGateCache().size == 0
    assert RATE_LIMIT_COUNTER_SCAN_PATTERN == "neuro:*:limit:*"
