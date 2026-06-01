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


def test_rate_limiter_facade_patch_point_supports_exceeded_denial(monkeypatch) -> None:
    from app.modules.neuro_commenting import rate_limiter
    from app.modules.neuro_commenting.rate_limiter import NeuroCommentRateLimiter, RateLimitScope
    from tests.test_neuro_commenting_rate_limiter import FakeRedis

    redis = FakeRedis()
    monkeypatch.setattr(rate_limiter, "redis_from_url", lambda: redis)
    limiter = NeuroCommentRateLimiter(
        limits=[
            {
                "scope_type": "account",
                "scope_id": "account-1",
                "limit_type": "comments_per_hour",
                "max_value": 1,
                "window_seconds": 3600,
            }
        ]
    )
    scope = RateLimitScope(
        workspace_id="workspace-1",
        campaign_id="campaign-1",
        account_id="account-1",
        target_id="target-1",
    )

    first = limiter.reserve(scope)
    limiter.commit(first)
    denied = limiter.reserve(scope)

    assert first.allowed is True
    assert denied.allowed is False
    assert denied.reason == "account comments_per_hour limit exceeded"
