from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base
from app.main import app
from app.models import (
    DEFAULT_LOCAL_WORKSPACE_ID,
    Asset,
    AssetKind,
    AssetStatus,
    Job,
    JobState,
    User,
    Workspace,
    WorkspaceMember,
    WorkspacePlan,
)
from app.services.accounts import create_account
from app.services.audit_logs import log_audit_event
from app.services.auth_batches import PhoneInput, create_auth_batch
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.database import create_sqlite_test_session_factory
from app.services.jobs import create_profile_job
from app.services.limits import WorkspaceLimitError, check_workspace_limit, increment_usage
from app.services.supabase_jwt import SupabaseJwtVerifier, clear_jwks_cache
from app.services.workspaces import ensure_default_workspace

from conftest import FakeExecutionUsableAdapter, override_app_session


def _rsa_jwk(kid: str) -> dict[str, str]:
    return {"kid": kid, "kty": "RSA", "alg": "RS256", "n": "AQ", "e": "AQAB"}


def test_db_config_prefers_runtime_and_direct_urls() -> None:
    config = Settings(
        database_url="postgresql+psycopg://local",
        database_runtime_url="postgresql+psycopg://pooled",
        database_direct_url="postgresql+psycopg://direct",
    )

    assert config.runtime_database_url == "postgresql+psycopg://pooled"
    assert config.migration_database_url == "postgresql+psycopg://direct"


def test_local_auth_allowed_in_local_and_development_modes() -> None:
    assert Settings(app_env="local", auth_mode="local").auth_mode == "local"
    assert Settings(app_env="development", auth_mode="local").auth_mode == "local"


def test_local_auth_blocked_in_production() -> None:
    try:
        Settings(app_env="production", auth_mode="local")
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "AUTH_MODE=local is not allowed" in message


def test_local_auth_blocked_with_neon_connection_mode() -> None:
    try:
        Settings(app_env="development", db_connection_mode="neon", auth_mode="local")
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "AUTH_MODE=local is not allowed" in message


def test_cloud_config_rejects_localhost_guard_and_wildcard_cors() -> None:
    for kwargs in (
        {"enforce_localhost_only": True, "cors_origins": "https://dashboard.example.com"},
        {"enforce_localhost_only": False, "cors_origins": ""},
        {"enforce_localhost_only": False, "cors_origins": "*"},
        {
            "enforce_localhost_only": False,
            "cors_origins": "https://dashboard.example.com",
            "stale_job_reaper_enabled": True,
        },
    ):
        try:
            values = {
                "app_env": "staging",
                "auth_mode": "supabase_jwt",
                "db_connection_mode": "neon",
                "stale_job_reaper_enabled": False,
            }
            values.update(kwargs)
            Settings(
                **values,
            )
        except ValueError as exc:
            message = str(exc)
        else:
            message = ""

        assert "cloud API requires" in message


def test_cloud_config_requires_operator_api_token() -> None:
    try:
        Settings(
            app_env="production",
            auth_mode="supabase_jwt",
            enforce_localhost_only=False,
            cors_origins="https://dashboard.example.com",
            stale_job_reaper_enabled=False,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "OPERATOR_API_TOKEN" in message


def test_cloud_config_requires_proxy_credentials_encryption_key() -> None:
    try:
        Settings(
            app_env="production",
            auth_mode="supabase_jwt",
            enforce_localhost_only=False,
            cors_origins="https://dashboard.example.com",
            stale_job_reaper_enabled=False,
            operator_api_token="operator-token-value",
            proxy_credentials_encryption_key=None,
        )
    except ValueError as exc:
        message = str(exc)
    else:
        message = ""

    assert "PROXY_CREDENTIALS_ENCRYPTION_KEY" in message


def test_supabase_auth_allowed_in_production() -> None:
    config = Settings(
        app_env="production",
        auth_mode="supabase_jwt",
        enforce_localhost_only=False,
        cors_origins="https://dashboard.example.com",
        stale_job_reaper_enabled=False,
        operator_api_token="operator-token-value",
        proxy_credentials_encryption_key="lNK8NBJDS69pUgNfeH0oLVg9-p3rU92YJ2OYQwj-GNg=",
    )

    assert config.auth_mode == "supabase_jwt"


def test_local_auth_override_allows_controlled_production_testing() -> None:
    config = Settings(
        app_env="production",
        auth_mode="local",
        allow_local_auth_in_prod=True,
        enforce_localhost_only=False,
        cors_origins="https://dashboard.example.com",
        stale_job_reaper_enabled=False,
        operator_api_token="operator-token-value",
        proxy_credentials_encryption_key="lNK8NBJDS69pUgNfeH0oLVg9-p3rU92YJ2OYQwj-GNg=",
    )

    assert config.allow_local_auth_in_prod is True


def test_default_workspace_bootstrap_creates_identity_graph(db_session) -> None:
    user, workspace, member = ensure_default_workspace(db_session)
    db_session.commit()

    assert user.external_auth_provider == "local"
    assert workspace.id == DEFAULT_LOCAL_WORKSPACE_ID
    assert member.role == "owner"
    assert db_session.get(WorkspacePlan, DEFAULT_LOCAL_WORKSPACE_ID) is not None


def test_local_auth_context_uses_default_workspace(db_session) -> None:
    class DummyRequest:
        headers: dict[str, str] = {}

    context = get_current_auth_context(DummyRequest(), db_session)

    assert context.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert context.role == "owner"
    assert context.auth_source == "local"


def test_local_auth_context_does_not_call_jwks(db_session, monkeypatch) -> None:
    class DummyRequest:
        headers: dict[str, str] = {}

    monkeypatch.setattr(
        "app.services.supabase_jwt.SupabaseJwtVerifier.from_settings",
        lambda settings: (_ for _ in ()).throw(AssertionError("JWKS should not be used in local auth mode")),
    )

    context = get_current_auth_context(DummyRequest(), db_session)

    assert context.auth_source == "local"


def test_supabase_jwt_verifier_accepts_rs256_mocked_valid_claims(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks")
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"sub": "u", "exp": 9999999999}, b"sig", b"a.b"))
    monkeypatch.setattr("app.services.supabase_jwt._load_jwks", lambda url, **kwargs: {"keys": [_rsa_jwk("k")]})

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._rsa_public_key_from_jwk", lambda jwk: FakePublicKey())

    assert verifier.verify("token")["sub"] == "u"


def test_supabase_jwt_verifier_accepts_es256_when_jwks_key_allows_it(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks")
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "ES256", "kid": "k"}, {"sub": "u", "exp": 9999999999}, b"\x00" * 64, b"a.b"))
    monkeypatch.setattr(
        "app.services.supabase_jwt._load_jwks",
        lambda url, **kwargs: {
            "keys": [{"kid": "k", "kty": "EC", "alg": "ES256", "crv": "P-256", "x": "AQ", "y": "AQ"}]
        },
    )

    class FakePublicKey:
        def verify(self, signature, signing_input, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._ec_public_key_from_jwk", lambda jwk: FakePublicKey(), raising=False)

    assert verifier.verify("token")["sub"] == "u"


def test_supabase_jwt_verifier_rejects_unsupported_algorithm(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks")
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "none", "kid": "k"}, {"sub": "u", "exp": 9999999999}, b"", b"a.b"))
    monkeypatch.setattr(
        "app.services.supabase_jwt._load_jwks",
        lambda url, **kwargs: {"keys": [_rsa_jwk("k")]},
    )

    try:
        verifier.verify("token")
    except Exception as exc:
        code = getattr(exc, "error_code", "")
    else:
        code = ""

    assert code == "JWT_ALG_UNSUPPORTED"


def test_supabase_jwt_verifier_uses_jwks_cache(monkeypatch) -> None:
    clear_jwks_cache()
    calls: list[str] = []
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks", cache_ttl_seconds=600)
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"sub": "u", "exp": 9999999999}, b"sig", b"a.b"))
    monkeypatch.setattr(
        "app.services.supabase_jwt._load_jwks",
        lambda url, **kwargs: calls.append(url) or {"keys": [_rsa_jwk("k")]},
    )

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._rsa_public_key_from_jwk", lambda jwk: FakePublicKey())

    assert verifier.verify("token")["sub"] == "u"
    assert verifier.verify("token")["sub"] == "u"
    assert calls == ["https://example.test/jwks"]


def test_supabase_jwt_verifier_refetches_after_ttl(monkeypatch) -> None:
    clear_jwks_cache()
    calls: list[str] = []
    times = iter([1000.0, 1000.0, 1002.0, 1002.0])
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks", cache_ttl_seconds=1)
    monkeypatch.setattr("app.services.supabase_jwt.time.time", lambda: next(times))
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"sub": "u", "exp": 9999999999}, b"sig", b"a.b"))
    monkeypatch.setattr(
        "app.services.supabase_jwt._load_jwks",
        lambda url, **kwargs: calls.append(url) or {"keys": [_rsa_jwk("k")]},
    )

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._rsa_public_key_from_jwk", lambda jwk: FakePublicKey())

    verifier.verify("token")
    verifier.verify("token")

    assert calls == ["https://example.test/jwks", "https://example.test/jwks"]


def test_supabase_jwt_verifier_refreshes_on_kid_miss(monkeypatch) -> None:
    clear_jwks_cache()
    responses = iter([
        {"keys": [_rsa_jwk("old")]},
        {"keys": [_rsa_jwk("new")]},
    ])
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks", cache_ttl_seconds=600)
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "new"}, {"sub": "u", "exp": 9999999999}, b"sig", b"a.b"))
    monkeypatch.setattr("app.services.supabase_jwt._load_jwks", lambda url, **kwargs: next(responses))

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._rsa_public_key_from_jwk", lambda jwk: FakePublicKey())

    assert verifier.verify("token")["sub"] == "u"


def test_supabase_jwt_verifier_rejects_unknown_kid_after_refresh(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks")
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "missing"}, {"sub": "u", "exp": 9999999999}, b"sig", b"a.b"))
    monkeypatch.setattr("app.services.supabase_jwt._load_jwks", lambda url, **kwargs: {"keys": [_rsa_jwk("other")]})

    try:
        verifier.verify("token")
    except Exception as exc:
        code = getattr(exc, "error_code", "")
    else:
        code = ""

    assert code == "JWT_KEY_NOT_FOUND"


def test_supabase_jwt_verifier_rejects_invalid_issuer_and_audience(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks", issuer="issuer", audience="aud")
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"sub": "u", "exp": 9999999999, "iss": "bad", "aud": "bad"}, b"sig", b"a.b"))
    monkeypatch.setattr("app.services.supabase_jwt._load_jwks", lambda url, **kwargs: {"keys": [_rsa_jwk("k")]})

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._rsa_public_key_from_jwk", lambda jwk: FakePublicKey())

    try:
        verifier.verify("token")
    except Exception as exc:
        code = getattr(exc, "error_code", "")
    else:
        code = ""

    assert code == "JWT_ISSUER_INVALID"


def test_supabase_jwt_verifier_rejects_invalid_audience(monkeypatch) -> None:
    payload = {"sub": "u", "exp": 9999999999, "iss": "issuer", "aud": "bad"}
    verifier = _prepare_jwt_verifier_with_fake_pubkey(monkeypatch, payload=payload)
    try:
        verifier.verify("token")
    except Exception as exc:
        code = getattr(exc, "error_code", "")
    else:
        code = ""

    assert code == "JWT_AUDIENCE_INVALID"


def test_supabase_jwt_verifier_rejects_expired_token_and_missing_sub(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks")
    monkeypatch.setattr("app.services.supabase_jwt._load_jwks", lambda url, **kwargs: {"keys": [_rsa_jwk("k")]})

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr("app.services.supabase_jwt._rsa_public_key_from_jwk", lambda jwk: FakePublicKey())
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"sub": "u", "exp": 1}, b"sig", b"a.b"))
    try:
        verifier.verify("expired")
    except Exception as exc:
        expired_code = getattr(exc, "error_code", "")
    else:
        expired_code = ""

    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"exp": 9999999999}, b"sig", b"a.b"))
    try:
        verifier.verify("missing-sub")
    except Exception as exc:
        missing_sub_code = getattr(exc, "error_code", "")
    else:
        missing_sub_code = ""

    assert expired_code == "JWT_EXPIRED"
    assert missing_sub_code == "JWT_SUB_MISSING"


def test_supabase_jwt_verifier_rejects_network_failure(monkeypatch) -> None:
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(jwks_url="https://example.test/jwks", max_retries=0)
    monkeypatch.setattr("app.services.supabase_jwt._split_jwt", lambda token: ({"alg": "RS256", "kid": "k"}, {"sub": "u", "exp": 9999999999}, b"sig", b"a.b"))

    def fail_fetch(url, **kwargs):
        from urllib.error import URLError

        raise URLError("offline")

    monkeypatch.setattr("app.services.supabase_jwt.urlopen", lambda *args, **kwargs: fail_fetch(*args, **kwargs))

    try:
        verifier.verify("token")
    except Exception as exc:
        code = getattr(exc, "error_code", "")
    else:
        code = ""

    assert code == "JWT_JWKS_FETCH_FAILED"


def test_account_endpoint_blocks_foreign_workspace_account() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        account = create_account(session, external_ref="+15550109999", workspace_id=workspace.id)
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).get(f"/api/accounts/{account_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert account_id not in response.text


def test_cannot_create_job_for_foreign_account() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        account = create_account(session, external_ref="+15550108888", workspace_id=workspace.id)
        account.account_state = "execution_usable"
        account.runtime_state.runtime_health = "ready"
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).post(
            "/api/jobs/profile",
            json={"account_id": account_id, "name": "Stylist", "bio": None, "username": None, "photo_asset_id": None},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert account_id not in response.text


def test_same_external_ref_allowed_across_workspaces() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        first = create_account(session, external_ref="+15550101111")
        second = create_account(session, external_ref="+15550101111", workspace_id=workspace.id)

    assert first.workspace_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert second.workspace_id == workspace.id


def test_cannot_access_foreign_asset() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        asset = Asset(
            workspace_id=workspace.id,
            kind=AssetKind.PROFILE_PHOTO,
            source_path="assets/source.jpg",
            normalized_path="assets/photo.jpg",
            content_hash="hash",
            mime="image/jpeg",
            status=AssetStatus.NORMALIZED,
        )
        session.add(asset)
        session.commit()
        asset_id = asset.id

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).get(f"/api/assets/{asset_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert asset_id not in response.text


def test_cannot_update_foreign_proxy() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        account = create_account(session, external_ref="+15550107777", workspace_id=workspace.id)
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).put(
            f"/api/accounts/{account_id}/proxy",
            json={"proxy_type": "http", "host": "127.0.0.1", "port": 8080},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert account_id not in response.text


def test_cannot_read_foreign_operation_logs() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        account = create_account(session, external_ref="+15550106666", workspace_id=workspace.id)
        log_audit_event(
            session,
            workspace_id=workspace.id,
            actor_user_id=None,
            action="account.created",
            entity_type="account",
            entity_id=account.id,
        )
        from app.services.operation_logs import log_operation

        log_operation(
            session,
            account_id=account.id,
            operation_type="proxy",
            status="completed",
            source="test",
            message="hidden",
        )
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).get("/api/operation-logs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_cannot_read_foreign_account_runtime_diagnostics() -> None:
    account_id = _setup_foreign_account_scenario(external_ref="+15550106111")
    try:
        response = TestClient(app).get(f"/api/accounts/{account_id}/runtime-diagnostics")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert account_id not in response.text


def test_cannot_read_foreign_account_jobs() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        account = create_account(session, external_ref="+15550106000", workspace_id=workspace.id)
        job = Job(
            workspace_id=workspace.id,
            account_id=account.id,
            job_state=JobState.COMPLETED,
            execution_intent_hash="foreign-job",
            payload_json={},
            plan_json_snapshot={"steps": []},
        )
        session.add(job)
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).get(f"/api/accounts/{account_id}/jobs")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert account_id not in response.text


def test_cannot_read_foreign_proxy() -> None:
    account_id = _setup_foreign_account_scenario(external_ref="+15550105999")
    try:
        response = TestClient(app).get(f"/api/accounts/{account_id}/proxy")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert account_id not in response.text


def test_cannot_poll_foreign_auth_batch() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        batch, _ = create_auth_batch(
            session,
            idempotency_key="foreign-batch",
            label="foreign",
            inputs=[PhoneInput(phone_number="+15550106555")],
            workspace_id=workspace.id,
        )
        batch_id = batch.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).get(f"/api/auth-batches/{batch_id}/poll")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert batch_id not in response.text


def test_same_idempotency_key_allowed_across_workspaces() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        foreign_batch, _ = create_auth_batch(
            session,
            idempotency_key="shared-cross-workspace-key",
            label="foreign",
            inputs=[PhoneInput(phone_number="+15550106556")],
            workspace_id=workspace.id,
        )
        session.commit()
        foreign_batch_id = foreign_batch.id

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).post(
            "/api/auth-batches",
            json={"idempotency_key": "shared-cross-workspace-key", "items": [{"phone_number": "+15550106656"}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    local_batch_id = response.json()["batch"]["id"]
    assert local_batch_id != foreign_batch_id
    assert "+15550106556" not in response.text


def test_validate_phones_does_not_leak_foreign_workspace_accounts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        create_account(session, external_ref="+15550109001", workspace_id=workspace.id)
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).post(
            "/api/auth-batches/validate-phones",
            json={"items": [{"phone_number": "+15550109001"}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["existing_accounts"] == []
    assert payload["valid_items"][0]["phone_number"] == "+15550109001"


def test_validate_phones_does_not_leak_foreign_workspace_batch_conflicts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        create_auth_batch(
            session,
            idempotency_key="foreign-active-batch",
            label="foreign",
            inputs=[PhoneInput(phone_number="+15550109002")],
            workspace_id=workspace.id,
        )
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).post(
            "/api/auth-batches/validate-phones",
            json={"items": [{"phone_number": "+15550109002"}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_batch_conflicts"] == []
    assert payload["valid_items"][0]["phone_number"] == "+15550109002"


def test_validate_phones_returns_own_workspace_conflicts() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _seed_second_workspace(session)
        create_account(session, external_ref="+15550109003")
        batch, _ = create_auth_batch(
            session,
            idempotency_key="own-active-batch",
            label="own",
            inputs=[PhoneInput(phone_number="+15550109004")],
        )
        session.commit()
        batch_id = batch.id

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).post(
            "/api/auth-batches/validate-phones",
            json={"items": [{"phone_number": "+15550109003"}, {"phone_number": "+15550109004"}]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["existing_accounts"]) == 1
    assert payload["existing_accounts"][0]["phone_number"] == "+15550109003"
    assert len(payload["active_batch_conflicts"]) == 1
    assert payload["active_batch_conflicts"][0]["phone_number"] == "+15550109004"
    assert payload["active_batch_conflicts"][0]["batch_id"] == batch_id


def test_auth_batch_viewer_receives_phone_hint_not_full_number() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        batch, _ = create_auth_batch(
            session,
            idempotency_key="viewer-phone-mask",
            label="mask",
            inputs=[PhoneInput(phone_number="+15550106666")],
        )
        batch_id = batch.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="viewer-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="viewer",
        auth_source="test",
    )
    try:
        snapshot = TestClient(app).get(f"/api/auth-batches/{batch_id}")
        poll = TestClient(app).get(f"/api/auth-batches/{batch_id}/poll")
    finally:
        app.dependency_overrides.clear()

    assert snapshot.status_code == 200
    assert poll.status_code == 200
    for payload in (snapshot.json(), poll.json()):
        item = payload["items"][0]
        assert item["phone_number"] is None
        assert item["phone_hint"] == "***6666"
        assert "+1555" not in item["phone_hint"]


def test_auth_batch_operator_receives_full_phone_number() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        batch, _ = create_auth_batch(
            session,
            idempotency_key="operator-phone-full",
            label="full",
            inputs=[PhoneInput(phone_number="+15550107777")],
        )
        batch_id = batch.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="operator-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="operator",
        auth_source="test",
    )
    try:
        response = TestClient(app).get(f"/api/auth-batches/{batch_id}/poll")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["phone_number"] == "+15550107777"
    assert item["phone_hint"] == "***7777"


def test_cannot_submit_code_for_foreign_auth_batch_item() -> None:
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        batch, _ = create_auth_batch(
            session,
            idempotency_key="foreign-item",
            label="foreign",
            inputs=[PhoneInput(phone_number="+15550106444")],
            workspace_id=workspace.id,
        )
        batch_id = batch.id
        item_id = batch.items[0].id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    try:
        response = TestClient(app).post(
            f"/api/auth-batches/{batch_id}/items/{item_id}/submit-code",
            json={"code": "12345", "idempotency_key": "submit-foreign"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert batch_id not in response.text


def test_job_creation_sets_workspace_and_actor(db_session) -> None:
    account = create_account(db_session, external_ref="+15550105555")
    account.account_state = "execution_usable"
    db_session.commit()

    job = create_profile_job(
        db_session,
        account_id=account.id,
        payload={"name": "Stylist", "bio": None, "username": None, "photo_asset_id": None},
        execution_adapter=FakeExecutionUsableAdapter(),
        requested_by_user_id="user-1",
    )

    assert job.workspace_id == account.workspace_id
    assert job.requested_by_user_id == "user-1"


def test_worker_rejects_workspace_account_mismatch(db_session) -> None:
    account = create_account(db_session, external_ref="+15550104444")
    job = Job(
        workspace_id="00000000-0000-4000-8000-000000000999",
        account_id=account.id,
        job_state=JobState.QUEUED,
        execution_intent_hash="hash",
        payload_json={},
        plan_json_snapshot={"steps": []},
    )
    db_session.add(job)
    db_session.commit()

    from app.workers.profile_jobs import execute_profile_job

    assert execute_profile_job(job.id, session=db_session) == 1
    assert job.failure_reason == "workspace_account_mismatch"


def test_audit_log_sanitizes_nested_metadata(db_session) -> None:
    ensure_default_workspace(db_session)
    row = log_audit_event(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id=None,
        action="proxy.updated",
        entity_type="proxy",
        metadata={"proxy_password": "secret", "nested": [{"jwt": "token"}]},
    )

    assert row.metadata_json == {"proxy_password": "***", "nested": [{"jwt": "***"}]}


def test_basic_limits_service_blocks_account_limit(db_session) -> None:
    ensure_default_workspace(db_session)
    plan = db_session.get(WorkspacePlan, DEFAULT_LOCAL_WORKSPACE_ID)
    plan.max_accounts = 0
    db_session.commit()

    try:
        check_workspace_limit(db_session, DEFAULT_LOCAL_WORKSPACE_ID, "accounts")
    except WorkspaceLimitError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "accounts limit exceeded"


def test_usage_counter_increments(db_session) -> None:
    ensure_default_workspace(db_session)

    counter = increment_usage(db_session, DEFAULT_LOCAL_WORKSPACE_ID, "jobs_per_day", value=2)

    assert counter.value == 2


def _prepare_jwt_verifier_with_fake_pubkey(monkeypatch, *, payload: dict) -> SupabaseJwtVerifier:
    """Build a JWT verifier with monkeypatched JWKS + fake RSA public key for negative cases."""
    clear_jwks_cache()
    verifier = SupabaseJwtVerifier(
        jwks_url="https://example.test/jwks", issuer="issuer", audience="aud",
    )
    monkeypatch.setattr(
        "app.services.supabase_jwt._split_jwt",
        lambda token: ({"alg": "RS256", "kid": "k"}, payload, b"sig", b"a.b"),
    )
    monkeypatch.setattr(
        "app.services.supabase_jwt._load_jwks",
        lambda url, **kwargs: {"keys": [_rsa_jwk("k")]},
    )

    class FakePublicKey:
        def verify(self, signature, signing_input, padding, algorithm):
            return None

    monkeypatch.setattr(
        "app.services.supabase_jwt._rsa_public_key_from_jwk",
        lambda jwk: FakePublicKey(),
    )
    return verifier


def _setup_foreign_account_scenario(*, external_ref: str) -> str:
    """Seed a foreign-workspace account and apply local-workspace auth overrides.

    Returns the foreign account id. Caller is responsible for clearing
    dependency_overrides via try/finally.
    """
    session_factory, engine = create_sqlite_test_session_factory()
    Base.metadata.create_all(engine)
    with session_factory() as session:
        _, workspace = _seed_second_workspace(session)
        account = create_account(session, external_ref=external_ref, workspace_id=workspace.id)
        account_id = account.id
        session.commit()

    override_app_session(session_factory)
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id="local-user",
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role="owner",
        auth_source="test",
    )
    return account_id


def _seed_second_workspace(session):
    ensure_default_workspace(session)
    user = User(
        email="second@example.test",
        external_auth_provider="test",
        external_auth_user_id="second-user",
        status="active",
    )
    workspace = Workspace(
        name="Second",
        slug="second",
        owner_user_id=user.id,
        status="active",
    )
    session.add(user)
    session.flush()
    workspace.owner_user_id = user.id
    session.add(workspace)
    session.flush()
    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    session.add(
        WorkspacePlan(
            workspace_id=workspace.id,
            plan_code="test",
            billing_status="active",
            max_accounts=1000,
            max_jobs_per_day=1000,
            max_batch_size=1000,
            max_storage_mb=1000,
            max_team_members=10,
        )
    )
    session.flush()
    return user, workspace
