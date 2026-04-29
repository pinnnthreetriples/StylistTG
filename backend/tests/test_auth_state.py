from collections import deque

from app.adapters.tdlib_auth import (
    TdlibAuthAdapter,
    TdlibAuthStatus,
    map_tdlib_error,
    map_authorization_state,
    normalize_phone_number,
    _tdlib_parameters_query,
)
from app.config import Settings
from app.models import AccountState


def test_phone_number_normalization_accepts_international_format() -> None:
    assert normalize_phone_number(" +1 (555) 010-2000 ") == "+15550102000"


def test_phone_number_normalization_rejects_local_format() -> None:
    try:
        normalize_phone_number("8 999 111 22 33")
    except ValueError as exc:
        assert "international format" in str(exc)
    else:
        raise AssertionError("local phone number was accepted")


def test_auth_state_mapping_for_supported_tdlib_states() -> None:
    wait_phone = map_authorization_state({"@type": "authorizationStateWaitPhoneNumber"})
    wait_code = map_authorization_state({"@type": "authorizationStateWaitCode"})
    ready = map_authorization_state({"@type": "authorizationStateReady"})
    closed = map_authorization_state({"@type": "authorizationStateClosed"})
    logging_out = map_authorization_state({"@type": "authorizationStateLoggingOut"})

    assert wait_phone.status == TdlibAuthStatus.WAIT_PHONE_NUMBER
    assert wait_phone.account_state == AccountState.AUTH_PENDING
    assert wait_code.status == TdlibAuthStatus.WAIT_CODE
    assert wait_code.account_state == AccountState.AWAITING_CODE
    assert ready.status == TdlibAuthStatus.READY
    assert ready.account_state == AccountState.AUTHORIZED_READY
    assert closed.status == TdlibAuthStatus.CLOSED
    assert closed.account_state == AccountState.REAUTH_REQUIRED
    assert logging_out.status == TdlibAuthStatus.CLOSED
    assert logging_out.account_state == AccountState.REAUTH_REQUIRED


def test_tdlib_parameters_use_stable_account_storage_and_test_dc_flag(tmp_path) -> None:
    config = Settings(
        tdlib_api_id=1,
        tdlib_api_hash="hash",
        tdlib_database_root=tmp_path / "database",
        tdlib_files_root=tmp_path / "files",
        tdlib_use_test_dc=True,
    )

    query = _tdlib_parameters_query(config, "account-1")

    assert query["use_test_dc"] is True
    assert query["database_directory"] == str(tmp_path / "database" / "account-1")
    assert query["files_directory"] == str(tmp_path / "files" / "account-1")


def test_wait_password_maps_to_awaiting_password() -> None:
    mapped = map_authorization_state({
        "@type": "authorizationStateWaitPassword",
        "password_hint": "my hint",
    })

    assert mapped.status == TdlibAuthStatus.WAIT_PASSWORD
    assert mapped.account_state == AccountState.AWAITING_PASSWORD
    assert mapped.needs_password is True
    assert mapped.password_hint == "my hint"


def test_frozen_tdlib_error_maps_to_manual_intervention() -> None:
    mapped = map_tdlib_error(
        {
            "@type": "error",
            "code": 420,
            "message": "FROZEN_METHOD_INVALID",
        }
    )

    assert mapped.account_state == AccountState.MANUAL_INTERVENTION_NEEDED
    assert mapped.runtime_health == "frozen"
    assert mapped.needs_manual_intervention is True
    assert mapped.recovery_marker == "tdlib_hard_stop:FROZEN_METHOD_INVALID"


def test_flood_tdlib_error_maps_to_manual_intervention() -> None:
    mapped = map_tdlib_error(
        {
            "@type": "error",
            "code": 420,
            "message": "PHONE_CODE_FLOOD",
        }
    )

    assert mapped.account_state == AccountState.MANUAL_INTERVENTION_NEEDED
    assert mapped.runtime_health == "flood"
    assert mapped.needs_manual_intervention is True
    assert mapped.recovery_marker == "tdlib_hard_stop:PHONE_CODE_FLOOD"


def test_unsupported_auth_branch_is_structured_not_crashing() -> None:
    mapped = map_authorization_state({"@type": "authorizationStateWaitEmailAddress"})

    assert mapped.status == TdlibAuthStatus.UNSUPPORTED
    assert mapped.account_state == AccountState.MANUAL_INTERVENTION_NEEDED
    assert mapped.needs_manual_intervention is True


class SharedQueueClient:
    def __init__(self, client_id: int, shared_events: deque[dict]) -> None:
        self.client_id = client_id
        self._shared_events = shared_events
        self.sent: list[dict] = []
        self.closed = False

    def send(self, query: dict) -> None:
        self.sent.append(query)

    def receive(self, timeout_seconds: float) -> dict | None:
        if self._shared_events:
            return self._shared_events.popleft()
        return None

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        self.sent.append(query)
        return {"id": 123456}

    def close(self) -> None:
        self.closed = True
        self.sent.append({"@type": "close"})


class SharedQueueClientFactory:
    def __init__(self, clients: list[SharedQueueClient]) -> None:
        self._clients = deque(clients)
        self.created: list[SharedQueueClient] = []

    def create(self, account_id: str) -> SharedQueueClient:
        client = self._clients.popleft()
        self.created.append(client)
        return client


def test_auth_adapter_ignores_stale_updates_from_previous_client(tmp_path) -> None:
    shared_events = deque(
        [
            {
                "@client_id": 1,
                "@type": "updateAuthorizationState",
                "authorization_state": {"@type": "authorizationStateClosed"},
            },
            {
                "@client_id": 1,
                "@type": "updateAuthorizationState",
                "authorization_state": {"@type": "authorizationStateClosing"},
            },
            {
                "@client_id": 2,
                "@type": "updateAuthorizationState",
                "authorization_state": {"@type": "authorizationStateWaitTdlibParameters"},
            },
            {
                "@client_id": 2,
                "@type": "updateAuthorizationState",
                "authorization_state": {"@type": "authorizationStateWaitPhoneNumber"},
            },
            {
                "@client_id": 2,
                "@type": "updateAuthorizationState",
                "authorization_state": {"@type": "authorizationStateWaitCode"},
            },
        ]
    )
    client_one = SharedQueueClient(1, shared_events)
    client_two = SharedQueueClient(2, shared_events)
    adapter = TdlibAuthAdapter(
        client_factory=SharedQueueClientFactory([client_one, client_two]),
        config=Settings(
            tdlib_api_id=1,
            tdlib_api_hash="hash",
            tdlib_database_root=tmp_path / "database",
            tdlib_files_root=tmp_path / "files",
            tdlib_auth_timeout_seconds=1.0,
            tdlib_receive_timeout_seconds=0.01,
        ),
    )

    result = adapter.start_otp("account-1", "+15550102000")

    assert result.status == TdlibAuthStatus.WAIT_CODE
    assert result.account_state == AccountState.AWAITING_CODE
    assert any(query.get("@type") == "setTdlibParameters" for query in client_two.sent)
    assert any(query.get("@type") == "setAuthenticationPhoneNumber" for query in client_two.sent)
