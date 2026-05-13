import json

import pytest
from pydantic_settings import SettingsConfigDict

from app.config import Settings
from app.adapters.tdlib_auth import RealTdJsonClient, TdlibAuthResult, TdlibAuthStatus
from app.models import AccountAuthAttempt, AccountState
from app.services.auth import (
    AuthSafetyError,
    confirm_otp,
    get_auth_state,
    mask_external_ref,
    start_otp,
    submit_password,
)

from conftest import FakeProfileSyncAdapter, FakeTdlibAuthAdapter
from helpers.factories import seed_two_workspaces


class LocalSettings(Settings):
    model_config = SettingsConfigDict(env_file=None)


class FakeTdJsonLibrary:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.response_extra: str | None = None

    def td_json_client_create(self):
        return object()

    def td_json_client_send(self, client, raw: bytes) -> None:
        query = json.loads(raw.decode("utf-8"))
        self.sent.append(query)
        self.response_extra = query.get("@extra")

    def td_json_client_receive(self, client, timeout_seconds: float) -> bytes | None:
        if len(self.sent) == 1 and self.response_extra:
            self.sent.append({"buffered_update_emitted": True})
            return json.dumps({"@type": "updateStoryPostSucceeded", "old_story_id": 42}).encode(
                "utf-8"
            )
        if self.response_extra:
            extra = self.response_extra
            self.response_extra = None
            return json.dumps({"@type": "ok", "@extra": extra}).encode("utf-8")
        return None

    def td_json_client_destroy(self, client) -> None:
        pass


def test_real_tdjson_client_buffers_updates_seen_during_send_query() -> None:
    client = RealTdJsonClient(FakeTdJsonLibrary())

    response = client.send_query({"@type": "getMe"}, 0.1)

    assert response["@type"] == "ok"
    assert client.receive(0)["@type"] == "updateStoryPostSucceeded"


def test_start_otp_creates_account_and_materializes_awaiting_code(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()

    result = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    assert result.account.account_state == AccountState.AWAITING_CODE
    assert result.account.external_ref == "+15550102000"
    assert result.runtime_state.session_present is True
    assert result.runtime_state.runtime_health == "awaiting_code"
    assert result.needs_code is True
    assert adapter.started == [(result.account.id, "+15550102000")]


def test_mask_external_ref_masks_phone_numbers_for_logs() -> None:
    assert mask_external_ref("+15550102000") == "+1555***2000"
    assert mask_external_ref("primary") == "pr***ry"


def test_start_otp_reuses_existing_awaiting_code_without_new_tdlib_request(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    first = start_otp(db_session, phone_number="+15550102000", adapter=adapter)
    adapter.started.clear()

    second = start_otp(
        db_session,
        phone_number="+15550102000",
        adapter=adapter,
        config=LocalSettings(auth_start_cooldown_seconds=0),
    )

    assert second.account.id == first.account.id
    assert second.account.account_state == AccountState.AWAITING_CODE
    assert second.needs_code is True
    assert adapter.started == []


def test_start_otp_reuses_existing_authorized_session_without_new_tdlib_request(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    started = start_otp(db_session, phone_number="+15550102000", adapter=adapter)
    confirm_otp(
        db_session,
        account_id=started.account.id,
        code="12345",
        adapter=adapter,
        profile_sync_adapter=FakeProfileSyncAdapter(),
    )
    adapter.started.clear()

    result = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    assert result.account.id == started.account.id
    assert result.account.account_state == AccountState.AUTHORIZED_READY
    assert result.needs_code is False
    assert adapter.started == []


def test_confirm_otp_materializes_authorized_ready(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    started = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    result = confirm_otp(
        db_session,
        account_id=started.account.id,
        code="12345",
        adapter=adapter,
        profile_sync_adapter=FakeProfileSyncAdapter(),
    )

    assert result.account.account_state == AccountState.AUTHORIZED_READY
    assert result.account.telegram_user_id == "123456"
    assert result.runtime_state.authorized_last_confirmed_at is not None
    assert result.runtime_state.runtime_health == "ready"
    assert adapter.confirmed == [(started.account.id, "12345")]
    assert result.account.profile_state is not None
    assert result.account.profile_state.first_name == "King"
    assert result.account.profile_state.last_name == "Blackburn"
    assert result.account.profile_state.username == "kingblackburn"
    assert result.account.profile_state.bio == "Live from Telegram"


def test_confirm_otp_rejects_account_outside_workspace(db_session) -> None:
    default_workspace_id, foreign_workspace_id = seed_two_workspaces(db_session)
    adapter = FakeTdlibAuthAdapter()
    started = start_otp(
        db_session,
        phone_number="+15550102000",
        adapter=adapter,
        workspace_id=default_workspace_id,
    )
    adapter.confirmed.clear()

    with pytest.raises(ValueError, match="account not found"):
        confirm_otp(
            db_session,
            account_id=started.account.id,
            code="12345",
            adapter=adapter,
            workspace_id=foreign_workspace_id,
        )

    assert adapter.confirmed == []


def test_submit_password_rejects_account_outside_workspace(db_session) -> None:
    default_workspace_id, foreign_workspace_id = seed_two_workspaces(db_session)
    adapter = FakeTdlibAuthAdapter()
    started = start_otp(
        db_session,
        phone_number="+15550102000",
        adapter=adapter,
        workspace_id=default_workspace_id,
    )

    with pytest.raises(ValueError, match="account not found"):
        submit_password(
            db_session,
            account_id=started.account.id,
            password="secret",
            adapter=adapter,
            workspace_id=foreign_workspace_id,
        )

    assert adapter.passwords == []


def test_closed_state_materializes_reauth_required(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.CLOSED,
        account_state=AccountState.REAUTH_REQUIRED,
        runtime_health="closed",
        needs_code=False,
        session_present=False,
        reauth_required=True,
        recovery_marker="tdlib_closed_recreate_required",
    )

    result = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    assert result.account.account_state == AccountState.REAUTH_REQUIRED
    assert result.runtime_state.reauth_required is True
    assert result.runtime_state.recovery_marker == "tdlib_closed_recreate_required"


def test_start_otp_allows_new_tdlib_request_after_reauth_required(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.CLOSED,
        account_state=AccountState.REAUTH_REQUIRED,
        runtime_health="closed",
        needs_code=False,
        session_present=False,
        reauth_required=True,
        recovery_marker="tdlib_closed_recreate_required",
    )
    first = start_otp(db_session, phone_number="+15550102000", adapter=adapter)
    adapter.started.clear()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.WAIT_CODE,
        account_state=AccountState.AWAITING_CODE,
        runtime_health="awaiting_code",
        needs_code=True,
        session_present=True,
        recovery_marker="tdlib_wait_code",
    )

    second = start_otp(
        db_session,
        phone_number="+15550102000",
        adapter=adapter,
        config=LocalSettings(auth_start_cooldown_seconds=0),
    )

    assert second.account.id == first.account.id
    assert second.account.account_state == AccountState.AWAITING_CODE
    assert adapter.started == [(first.account.id, "+15550102000")]


def test_start_otp_blocks_reauth_retry_during_cooldown(db_session) -> None:
    config = LocalSettings(auth_start_cooldown_seconds=120)
    adapter = FakeTdlibAuthAdapter()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.CLOSED,
        account_state=AccountState.REAUTH_REQUIRED,
        runtime_health="closed",
        needs_code=False,
        session_present=False,
        reauth_required=True,
        recovery_marker="tdlib_closed_recreate_required",
    )
    first = start_otp(db_session, phone_number="+15550102000", adapter=adapter, config=config)
    adapter.started.clear()

    with pytest.raises(AuthSafetyError, match="wait before requesting"):
        start_otp(db_session, phone_number="+15550102000", adapter=adapter, config=config)

    assert adapter.started == []
    assert db_session.query(AccountAuthAttempt).filter_by(account_id=first.account.id).count() == 1


def test_start_otp_blocks_after_daily_attempt_cap(db_session) -> None:
    config = LocalSettings(auth_daily_start_limit=1, auth_start_cooldown_seconds=0)
    adapter = FakeTdlibAuthAdapter()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.CLOSED,
        account_state=AccountState.REAUTH_REQUIRED,
        runtime_health="closed",
        needs_code=False,
        session_present=False,
        reauth_required=True,
        recovery_marker="tdlib_closed_recreate_required",
    )
    first = start_otp(db_session, phone_number="+15550102000", adapter=adapter, config=config)
    adapter.started.clear()

    with pytest.raises(AuthSafetyError, match="daily Telegram login attempt limit"):
        start_otp(db_session, phone_number="+15550102000", adapter=adapter, config=config)

    assert adapter.started == []
    assert db_session.query(AccountAuthAttempt).filter_by(account_id=first.account.id).count() == 1


def test_start_otp_blocks_when_production_auth_disabled(db_session) -> None:
    config = LocalSettings(tdlib_production_auth_enabled=False, tdlib_use_test_dc=False)
    adapter = FakeTdlibAuthAdapter()

    with pytest.raises(AuthSafetyError, match="production TDLib auth is disabled"):
        start_otp(db_session, phone_number="+15550102000", adapter=adapter, config=config)

    assert adapter.started == []


def test_start_otp_blocks_manual_intervention_state(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    result = start_otp(db_session, phone_number="+15550102000", adapter=adapter)
    result.account.account_state = AccountState.MANUAL_INTERVENTION_NEEDED
    result.runtime_state.runtime_health = "frozen"
    result.runtime_state.recovery_marker = "tdlib_hard_stop:FROZEN_METHOD_INVALID"
    db_session.commit()
    adapter.started.clear()

    with pytest.raises(AuthSafetyError, match="manual intervention"):
        start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    assert adapter.started == []


def test_runtime_broken_materializes_structured_failure(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.BROKEN,
        account_state=AccountState.RUNTIME_BROKEN,
        runtime_health="broken",
        needs_code=False,
        session_present=False,
        error="tdjson unavailable",
        recovery_marker="tdlib_runtime_broken",
    )

    result = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    assert result.account.account_state == AccountState.RUNTIME_BROKEN
    assert result.runtime_state.runtime_health == "broken"
    assert result.error == "tdjson unavailable"


def test_frozen_result_materializes_manual_intervention_hard_stop(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    adapter.start_result = TdlibAuthResult(
        status=TdlibAuthStatus.UNSUPPORTED,
        account_state=AccountState.MANUAL_INTERVENTION_NEEDED,
        runtime_health="frozen",
        needs_code=False,
        session_present=True,
        reauth_required=True,
        needs_manual_intervention=True,
        recovery_marker="tdlib_hard_stop:FROZEN_METHOD_INVALID",
        error="FROZEN_METHOD_INVALID",
    )

    result = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    assert result.account.account_state == AccountState.MANUAL_INTERVENTION_NEEDED
    assert result.runtime_state.runtime_health == "manual_intervention_needed"
    assert result.runtime_state.reauth_required is True
    assert result.runtime_state.recovery_marker == "tdlib_hard_stop:FROZEN_METHOD_INVALID"


def test_get_auth_state_returns_materialized_runtime(db_session) -> None:
    adapter = FakeTdlibAuthAdapter()
    started = start_otp(db_session, phone_number="+15550102000", adapter=adapter)

    state = get_auth_state(db_session, started.account.id)

    assert state.account.id == started.account.id
    assert state.runtime_state.runtime_health == "awaiting_code"


def test_get_auth_state_rejects_account_outside_workspace(db_session) -> None:
    default_workspace_id, foreign_workspace_id = seed_two_workspaces(db_session)
    adapter = FakeTdlibAuthAdapter()
    started = start_otp(
        db_session,
        phone_number="+15550102000",
        adapter=adapter,
        workspace_id=default_workspace_id,
    )

    with pytest.raises(ValueError, match="account not found"):
        get_auth_state(db_session, started.account.id, workspace_id=foreign_workspace_id)
