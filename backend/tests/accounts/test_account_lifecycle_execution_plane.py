from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import AccountState, DEFAULT_LOCAL_WORKSPACE_ID
from app.services.account_cooldowns import create_cooldown_from_error, list_active_account_cooldowns
from app.modules.account_lifecycle.service import (
    build_account_export_payload,
    create_account_export_request,
)
from app.services.accounts import create_account
from app.services.locks import (
    acquire_redis_account_lock,
    refresh_redis_account_lock,
    release_redis_account_lock,
)
from app.services.rate_limits import evaluate_tenant_rate_limit
from app.services.retry_policy import classify_error_category, retry_policy_for
from app.services.risk_gate import evaluate_action_gate
from app.services.production_reaper import run_reaper_report
from app.services.scheduler import scheduler_report
from app.services.sensitive_audit import record_sensitive_audit_event

from conftest import override_app_session


class FakeStorage:
    backend_name = "fake"

    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def save_bytes(self, key: str, content: bytes, **_kwargs):
        self.saved[key] = content
        return object()

    def delete(self, key: str) -> bool:
        self.deleted.append(key)
        return True


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        self.ttls[key] = ex or 0
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        if key not in self.values:
            return 0
        del self.values[key]
        return 1

    def expire(self, key, ttl):
        if key not in self.values:
            return 0
        self.ttls[key] = ttl
        return 1

    def incr(self, key):
        self.values[key] = str(int(self.values.get(key, "0")) + 1)
        return int(self.values[key])

    def ttl(self, key):
        return self.ttls.get(key, 3600)

    def pipeline(self):
        return FakeRedisPipeline(self)


class FakeRedisPipeline:
    def __init__(self, redis: FakeRedis) -> None:
        self.redis = redis
        self.commands = []

    def incr(self, key):
        self.commands.append(("incr", key))
        return self

    def expire(self, key, ttl, nx=False):
        self.commands.append(("expire", key, ttl, nx))
        return self

    def ttl(self, key):
        self.commands.append(("ttl", key))
        return self

    def execute(self):
        results = []
        for command in self.commands:
            name = command[0]
            if name == "incr":
                results.append(self.redis.incr(command[1]))
            elif name == "expire":
                _name, key, ttl, nx = command
                if nx and key in self.redis.ttls:
                    results.append(0)
                else:
                    results.append(self.redis.expire(key, ttl))
            elif name == "ttl":
                results.append(self.redis.ttl(command[1]))
        return results


def test_deletion_preview_is_tenant_scoped_and_secret_safe(db_session) -> None:
    account = create_account(db_session, external_ref="+15550103000")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.session_present = True
    account.runtime_state.runtime_health = "ready"
    db_session.commit()

    override_app_session(lambda: _session_context(db_session))
    try:
        response = TestClient(app).get(f"/api/accounts/{account.id}/deletion-preview")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_id"] == account.id
    assert payload["requires_confirmation"] is True
    assert "tdlib_session_dir" in {item["resource"] for item in payload["planned_actions"]}
    serialized = str(payload).lower()
    assert "tdlib/database" not in serialized
    assert "password" not in serialized


def test_deletion_request_requires_confirmation_and_audits(db_session) -> None:
    account = create_account(db_session, external_ref="+15550103001")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.session_present = True
    account.runtime_state.runtime_health = "ready"
    db_session.commit()

    override_app_session(lambda: _session_context(db_session))
    client = TestClient(app)
    try:
        rejected = client.post(
            f"/api/accounts/{account.id}/deletion-requests",
            json={
                "reason": "operator requested deletion",
                "confirmation": "WRONG",
                "dry_run": True,
            },
        )
        accepted = client.post(
            f"/api/accounts/{account.id}/deletion-requests",
            json={
                "reason": "operator requested deletion",
                "confirmation": "DELETE",
                "dry_run": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert rejected.status_code == 422
    rejected_body = rejected.json()
    assert rejected_body["error_code"] == "REQUEST_VALIDATION_ERROR"
    assert rejected_body["field_errors"][0]["field"] == "confirmation"
    assert accepted.status_code == 201
    payload = accepted.json()
    assert payload["status"] == "previewed"
    assert payload["dry_run_result"]["requires_confirmation"] is True
    audits = client_response_audits(db_session, account.id)
    assert "account.delete.requested" in {event.action for event in audits}
    assert db_session.get(type(account), account.id) is not None


def test_export_payload_redacts_secrets_and_excludes_sessions(db_session) -> None:
    account = create_account(db_session, external_ref="+15550103002")
    account.account_state = AccountState.EXECUTION_USABLE
    account.runtime_state.session_present = True
    account.runtime_state.runtime_health = "ready"
    db_session.commit()
    storage = FakeStorage()

    request = create_account_export_request(
        db_session,
        account_id=account.id,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        actor_user_id=None,
        storage=storage,
    )
    payload = build_account_export_payload(db_session, account=account)

    assert request.status == "completed"
    assert storage.saved
    serialized = str(payload).lower()
    assert "[excluded]" in serialized
    assert "[redacted]" in serialized
    assert "tdlib/database" not in serialized
    assert "proxy_password" not in serialized


def test_risk_gate_requires_override_for_high_risk_and_blocks_unsafe_critical(db_session) -> None:
    account = create_account(db_session, external_ref="+15550103003")
    account.account_state = AccountState.REAUTH_REQUIRED
    account.runtime_state.session_present = False
    account.runtime_state.runtime_health = "closed"
    account.runtime_state.reauth_required = True
    db_session.commit()

    blocked = evaluate_action_gate(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        action_type="profile.update",
    )
    allowed_delete = evaluate_action_gate(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        account_id=account.id,
        action_type="account.delete",
    )

    assert blocked["allowed"] is False
    assert blocked["blocked"] is True
    assert allowed_delete["allowed"] is True


def test_audit_metadata_is_sanitized(db_session) -> None:
    event = record_sensitive_audit_event(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        action="account.export.requested",
        entity_type="account",
        metadata={"token": "abc", "nested": {"proxy_password": "secret"}, "safe": "ok"},
    )
    db_session.flush()

    assert event.metadata_json["token"] == "***"
    assert event.metadata_json["nested"]["proxy_password"] == "***"
    assert event.metadata_json["safe"] == "ok"


def test_redis_account_lock_owner_and_ttl() -> None:
    redis = FakeRedis()
    first = acquire_redis_account_lock(
        redis,
        workspace_id="workspace",
        account_id="account",
        purpose="execution",
        ttl_seconds=30,
        owner="owner-1",
    )
    second = acquire_redis_account_lock(
        redis,
        workspace_id="workspace",
        account_id="account",
        purpose="execution",
        ttl_seconds=30,
        owner="owner-2",
    )

    assert first.acquired is True
    assert second.acquired is False
    assert first.key == "locks:account:workspace:account:execution"
    assert release_redis_account_lock(redis, second) is False
    assert refresh_redis_account_lock(redis, first, ttl_seconds=60) is True
    assert redis.ttls[first.key] == 60
    assert release_redis_account_lock(redis, first) is True


def test_rate_limit_blocks_over_limit_and_is_workspace_scoped() -> None:
    redis = FakeRedis()
    for _ in range(20):
        assert evaluate_tenant_rate_limit(
            redis, workspace_id="w1", action_type="account.auth", queue_name="auth_jobs"
        ).allowed
    blocked = evaluate_tenant_rate_limit(
        redis, workspace_id="w1", action_type="account.auth", queue_name="auth_jobs"
    )
    other_workspace = evaluate_tenant_rate_limit(
        redis, workspace_id="w2", action_type="account.auth", queue_name="auth_jobs"
    )

    assert blocked.allowed is False
    assert blocked.reason == "tenant_rate_limit_exceeded"
    assert blocked.retry_after_seconds is not None
    assert other_workspace.allowed is True


def test_flood_wait_cooldown_and_retry_policy(db_session) -> None:
    account = create_account(db_session, external_ref="+15550103004")
    cooldown = create_cooldown_from_error(
        db_session,
        account_id=account.id,
        operation="profile_update",
        error_code="FLOOD_WAIT_120",
    )
    db_session.commit()

    assert cooldown is not None
    active = list_active_account_cooldowns(db_session, account.id)
    assert active[0]["reason_code"] == "recent_flood_wait"
    assert classify_error_category("FLOOD_WAIT_120") == "flood_wait"
    policy = retry_policy_for("flood_wait")
    assert policy.retry is False
    assert policy.max_attempts == 1


def test_scheduler_and_reaper_default_to_safe_modes(db_session) -> None:
    report = scheduler_report()
    reaper = run_reaper_report(db_session, mode="dry_run")

    assert report.enabled is False
    assert report.destructive_actions_enabled is False
    assert reaper.mode == "dry_run"
    assert reaper.destructive_actions_enabled is False
    assert reaper.deleted_objects == 0


def test_legacy_delete_endpoint_requires_lifecycle_request(db_session) -> None:
    account = create_account(db_session, external_ref="+15550103005")
    db_session.commit()
    override_app_session(lambda: _session_context(db_session))
    try:
        response = TestClient(app).delete(f"/api/accounts/{account.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "ACCOUNT_DELETE_REQUIRES_REQUEST"


def client_response_audits(session, account_id: str):
    from app.models import SensitiveAuditEvent

    return session.query(SensitiveAuditEvent).filter_by(account_id=account_id).all()


def _session_context(session):
    class Context:
        def __enter__(self):
            return session

        def __exit__(self, *_args):
            return False

    return Context()
