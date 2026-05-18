# test-analyzer: disable-file=TQA040 reason="contract test - verifies proxy is configured before TDLib network calls; failure paths covered by test_tdlib_runtime_validation"
from collections import deque

from app.adapters.tdlib_auth import TdlibAuthAdapter
from app.adapters.tdlib_profile_execution import TdlibProfileExecutionAdapter
from app.adapters.tdlib_readonly_validity import TdlibReadOnlyValidityAdapter
from app.config import Settings


class OrderedTdlibClient:
    client_id = 1

    def __init__(self, states: list[str]) -> None:
        self._states = deque(states)
        self.calls: list[str] = []

    def send(self, query: dict) -> None:
        self.calls.append(query["@type"])

    def receive(self, timeout_seconds: float) -> dict | None:
        if not self._states:
            return None
        return {
            "@type": "updateAuthorizationState",
            "authorization_state": {"@type": self._states.popleft()},
        }

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        query_type = query["@type"]
        self.calls.append(query_type)
        if query_type == "addProxy":
            return {"@type": "proxy", "id": 7}
        if query_type == "enableProxy":
            return {"@type": "ok"}
        if query_type == "getMe":
            return {"@type": "user", "id": 123456, "first_name": "Stylist", "username": "stylisttg"}
        return {"@type": "ok"}

    def close(self) -> None:
        self.calls.append("close")


class OrderedTdlibClientFactory:
    def __init__(self, client: OrderedTdlibClient) -> None:
        self.client = client

    def create(self, account_id: str) -> OrderedTdlibClient:
        return self.client


def proxy_applier(client: OrderedTdlibClient, account_id: str) -> bool:
    response = client.send_query({"@type": "addProxy", "server": "127.0.0.1"}, 0.01)
    client.send_query({"@type": "enableProxy", "proxy_id": response["id"]}, 0.01)
    return True


def test_proxy_is_applied_before_otp_start_phone_submission(tmp_path) -> None:
    client = OrderedTdlibClient(
        [
            "authorizationStateWaitTdlibParameters",
            "authorizationStateWaitPhoneNumber",
            "authorizationStateWaitCode",
        ]
    )
    adapter = TdlibAuthAdapter(
        client_factory=OrderedTdlibClientFactory(client),
        config=_settings(tmp_path),
        proxy_applier=proxy_applier,
    )

    adapter.start_otp("account-1", "+15550102000")

    assert client.calls[:4] == [
        "setTdlibParameters",
        "addProxy",
        "enableProxy",
        "setAuthenticationPhoneNumber",
    ]


def test_proxy_is_applied_before_readonly_validity_get_me(tmp_path) -> None:
    client = OrderedTdlibClient(
        [
            "authorizationStateWaitTdlibParameters",
            "authorizationStateReady",
        ]
    )
    adapter = TdlibReadOnlyValidityAdapter(
        client_factory=OrderedTdlibClientFactory(client),
        config=_settings(tmp_path),
        proxy_applier=proxy_applier,
    )

    result = adapter.check_account("account-1")

    assert result["status"] == "valid"
    assert client.calls[:4] == [
        "setTdlibParameters",
        "addProxy",
        "enableProxy",
        "getMe",
    ]


def test_proxy_is_applied_before_profile_mutation_query(tmp_path) -> None:
    client = OrderedTdlibClient(
        [
            "authorizationStateWaitTdlibParameters",
            "authorizationStateReady",
        ]
    )
    adapter = TdlibProfileExecutionAdapter(
        client_factory=OrderedTdlibClientFactory(client),
        config=_settings(tmp_path),
        proxy_applier=proxy_applier,
    )

    events = list(
        adapter.execute(
            "account-1",
            {
                "steps": [
                    {
                        "step_key": "set_name",
                        "step_type": "set_name",
                        "payload": {"first_name": "Stylist", "last_name": "TG"},
                    }
                ]
            },
            {},
        )
    )

    assert events[-2]["event"] == "step_succeeded"
    assert client.calls[:4] == [
        "setTdlibParameters",
        "addProxy",
        "enableProxy",
        "setName",
    ]


def _settings(tmp_path) -> Settings:
    return Settings(
        tdlib_api_id=1,
        tdlib_api_hash="hash",
        tdlib_database_root=tmp_path / "database",
        tdlib_files_root=tmp_path / "files",
        tdlib_receive_timeout_seconds=0.01,
        tdlib_auth_timeout_seconds=1.0,
    )
