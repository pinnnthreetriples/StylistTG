from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest
from freezegun import freeze_time

from app.contracts.notifications import NotificationPayload
from app.main import app
from app.models import (
    DEFAULT_LOCAL_USER_ID,
    DEFAULT_LOCAL_WORKSPACE_ID,
    AccountQuarantine,
    AccountStatusObservation,
    AdminNotificationLog,
    NeuroCommentEvent,
    SensitiveAuditEvent,
    Workspace,
)
from app.services.admin_notifications import collect_triggers, deliver, is_recently_notified
from app.services.auth_context import AuthContext, get_current_auth_context
from app.services.notification_channels.email import EmailNotifier
from app.services.notification_channels.webhook import WebhookNotifier
from app.services.scheduler import (
    ADMIN_NOTIFICATION_JOB_ID_PREFIX,
    NOTIFICATION_COLLECTION_TICK_SECONDS,
    admin_notification_tick,
    enqueue_admin_notification_tick,
    scheduler_report,
)
from app.services.workspaces import ensure_default_workspace
from tests.helpers.factories import seed_account

_FROZEN_NOW = datetime(2026, 5, 22, 12, 0, tzinfo=UTC)


def _auth(role: str = "admin") -> AuthContext:
    return AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role=role,
        auth_source="test",
    )


@pytest.fixture()
def admin_client(app_client):
    app.dependency_overrides[get_current_auth_context] = lambda: _auth("admin")
    return app_client


def _seed_accounts(db_session, count: int) -> list[str]:
    return [
        seed_account(db_session, external_ref=f"+1555012{index:04d}").id for index in range(count)
    ]


def _payload() -> NotificationPayload:
    return NotificationPayload(
        workspace_id=UUID(DEFAULT_LOCAL_WORKSPACE_ID),
        trigger_code="quarantine_epidemic",
        severity="warning",
        title="Quarantine spike detected",
        body_text="More than 10% of workspace accounts entered quarantine.",
        metadata={"ratio": 0.11},
        triggered_at=_FROZEN_NOW,
    )


def _set_notification_webhook(db_session, url: str = "https://hooks.example.test/admin") -> None:
    ensure_default_workspace(db_session)
    workspace = db_session.get(Workspace, DEFAULT_LOCAL_WORKSPACE_ID)
    workspace.notification_webhook_url = url


def _webhook_channel(handler) -> WebhookNotifier:
    transport = httpx.MockTransport(handler)
    return WebhookNotifier(client=httpx.Client(transport=transport))


def _override_auth_role(role: str) -> None:
    app.dependency_overrides[get_current_auth_context] = lambda: AuthContext(
        user_id=DEFAULT_LOCAL_USER_ID,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        role=role,
        auth_source="test",
    )


@freeze_time(_FROZEN_NOW)
def test_quarantine_epidemic_trigger_emits_warning_payload(db_session) -> None:
    account_ids = _seed_accounts(db_session, 100)
    for account_id in account_ids[:11]:
        db_session.add(
            AccountQuarantine(
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=account_id,
                reason="manual",
                started_at=_FROZEN_NOW - timedelta(minutes=30),
                until=_FROZEN_NOW + timedelta(hours=1),
            )
        )
    db_session.commit()

    payloads = collect_triggers(db_session, now=_FROZEN_NOW)

    assert [payload.trigger_code for payload in payloads] == ["quarantine_epidemic"]
    assert payloads[0].severity == "warning"
    assert payloads[0].metadata["quarantined_accounts"] == 11


@freeze_time(_FROZEN_NOW)
def test_quarantine_epidemic_threshold_is_strictly_greater_than_ten_percent(db_session) -> None:
    account_ids = _seed_accounts(db_session, 100)
    for account_id in account_ids[:10]:
        db_session.add(
            AccountQuarantine(
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=account_id,
                reason="manual",
                started_at=_FROZEN_NOW - timedelta(minutes=30),
                until=_FROZEN_NOW + timedelta(hours=1),
            )
        )
    db_session.commit()

    assert collect_triggers(db_session, now=_FROZEN_NOW) == []


@freeze_time(_FROZEN_NOW)
def test_ggr_drop_trigger_is_skipped_until_history_table_exists(db_session) -> None:
    _seed_accounts(db_session, 1)

    payloads = collect_triggers(db_session, now=_FROZEN_NOW)

    assert "ggr_drop" not in {payload.trigger_code for payload in payloads}


@freeze_time(_FROZEN_NOW)
def test_gate_block_burst_trigger_emits_when_blocked_ratio_exceeds_threshold(db_session) -> None:
    ensure_default_workspace(db_session)
    for index in range(40):
        db_session.add(
            NeuroCommentEvent(
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                event_type="comment_send_blocked_by_gate",
                event_level="warning",
                message=f"blocked {index}",
                created_at=_FROZEN_NOW - timedelta(minutes=10),
            )
        )
    for index in range(60):
        db_session.add(
            NeuroCommentEvent(
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                event_type="comment_send_succeeded",
                event_level="info",
                message=f"sent {index}",
                created_at=_FROZEN_NOW - timedelta(minutes=10),
            )
        )
    db_session.commit()

    payloads = collect_triggers(db_session, now=_FROZEN_NOW)

    assert [payload.trigger_code for payload in payloads] == ["gate_block_burst"]
    assert payloads[0].metadata["blocked_ratio"] == 0.4


@freeze_time(_FROZEN_NOW)
def test_proxy_outage_trigger_emits_when_unhealthy_ratio_exceeds_threshold(db_session) -> None:
    account_id = _seed_accounts(db_session, 1)[0]
    for index in range(9):
        db_session.add(
            AccountStatusObservation(
                workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
                account_id=account_id,
                observed_at=_FROZEN_NOW - timedelta(minutes=5),
                proxy_healthy=False,
                tdlib_authorized=True,
                consecutive_failures=index,
            )
        )
    db_session.add(
        AccountStatusObservation(
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            account_id=account_id,
            observed_at=_FROZEN_NOW - timedelta(minutes=5),
            proxy_healthy=True,
            tdlib_authorized=True,
            consecutive_failures=0,
        )
    )
    db_session.commit()

    payloads = collect_triggers(db_session, now=_FROZEN_NOW)

    assert [payload.trigger_code for payload in payloads] == ["proxy_outage"]
    assert payloads[0].severity == "critical"
    assert payloads[0].metadata["unhealthy_ratio"] == 0.9


@freeze_time(_FROZEN_NOW)
def test_deduplication_detects_same_workspace_trigger_within_one_hour(db_session) -> None:
    ensure_default_workspace(db_session)
    db_session.add(
        AdminNotificationLog(
            workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
            trigger_code="quarantine_epidemic",
            triggered_at=_FROZEN_NOW - timedelta(minutes=30),
            metadata_json={},
            delivered_channels=["email"],
        )
    )
    db_session.commit()

    assert is_recently_notified(
        db_session,
        workspace_id=DEFAULT_LOCAL_WORKSPACE_ID,
        trigger_code="quarantine_epidemic",
    )


@freeze_time(_FROZEN_NOW)
def test_webhook_delivery_200_records_success_and_log_entry(db_session) -> None:
    _set_notification_webhook(db_session)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    result = deliver(
        db_session,
        _payload(),
        channels=[_webhook_channel(handler)],
    )

    assert result[0].channel == "webhook"
    assert result[0].success is True
    assert requests[0].url == "https://hooks.example.test/admin"
    log = db_session.query(AdminNotificationLog).one()
    assert log.delivered_channels == ["webhook"]


@freeze_time(_FROZEN_NOW)
def test_webhook_timeout_records_failure_and_log_entry(db_session) -> None:
    _set_notification_webhook(db_session)

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    result = deliver(
        db_session,
        _payload(),
        channels=[_webhook_channel(handler)],
    )

    assert result[0].channel == "webhook"
    assert result[0].success is False
    assert "timed out" in (result[0].error or "")
    log = db_session.query(AdminNotificationLog).one()
    assert log.delivered_channels == []


@freeze_time(_FROZEN_NOW)
def test_email_stub_returns_success_and_records_log_entry(db_session) -> None:
    ensure_default_workspace(db_session)

    result = deliver(db_session, _payload(), channels=[EmailNotifier()])

    assert result[0].channel == "email"
    assert result[0].success is True
    log = db_session.query(AdminNotificationLog).one()
    assert log.delivered_channels == ["email"]


@freeze_time(_FROZEN_NOW)
def test_patch_notification_settings_admin_updates_webhook_and_audits(
    admin_client,
    db_session,
) -> None:
    ensure_default_workspace(db_session)

    response = admin_client.patch(
        f"/api/workspaces/{DEFAULT_LOCAL_WORKSPACE_ID}/notification-settings",
        json={"notification_webhook_url": "https://hooks.example.test/admin"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["notification_webhook_url"] == "https://hooks.example.test/admin"
    workspace = db_session.get(Workspace, DEFAULT_LOCAL_WORKSPACE_ID)
    assert workspace.notification_webhook_url == "https://hooks.example.test/admin"
    event = db_session.query(SensitiveAuditEvent).one()
    assert event.action == "workspace.notification_webhook_url.updated"
    assert event.entity_type == "workspace"
    assert event.entity_id == DEFAULT_LOCAL_WORKSPACE_ID
    assert event.metadata_json == {
        "field": "notification_webhook_url",
        "new_value_set": True,
    }


def test_patch_notification_settings_non_admin_returns_403(app_client, db_session) -> None:
    ensure_default_workspace(db_session)
    _override_auth_role("operator")

    response = app_client.patch(
        f"/api/workspaces/{DEFAULT_LOCAL_WORKSPACE_ID}/notification-settings",
        json={"notification_webhook_url": "https://hooks.example.test/admin"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error_code"] == "ROLE_FORBIDDEN"
    assert body["error_class"] == "forbidden"


def test_patch_notification_settings_rejects_non_https_url(admin_client, db_session) -> None:
    ensure_default_workspace(db_session)

    response = admin_client.patch(
        f"/api/workspaces/{DEFAULT_LOCAL_WORKSPACE_ID}/notification-settings",
        json={"notification_webhook_url": "http://hooks.example.test/admin"},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "REQUEST_VALIDATION_ERROR"


def test_scheduler_report_registers_admin_notification_tick() -> None:
    report = scheduler_report()

    assert report.planned_ticks["admin_notifications"] == NOTIFICATION_COLLECTION_TICK_SECONDS


def test_enqueue_admin_notification_tick_uses_scheduler_queue_and_five_minute_bucket(
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    seen_queues: list[str] = []

    def fake_get_queue(name: str):
        seen_queues.append(name)
        return type(
            "FakeQueue", (), {"enqueue_call": lambda _self, **kwargs: calls.append(kwargs)}
        )()

    monkeypatch.setattr("app.job_queue.rq.get_queue", fake_get_queue)

    assert enqueue_admin_notification_tick(now=(NOTIFICATION_COLLECTION_TICK_SECONDS * 42) + 10)

    assert seen_queues == ["scheduler_jobs"]
    assert calls == [
        {
            "func": admin_notification_tick,
            "job_id": f"{ADMIN_NOTIFICATION_JOB_ID_PREFIX}-42",
            "unique": True,
        }
    ]
