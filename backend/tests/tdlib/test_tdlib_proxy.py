from app.config import Settings
from app.services.tdlib_proxy import TdlibProxySettings, apply_account_proxy_to_tdlib


class FakeProxyClient:
    def __init__(self) -> None:
        self.queries: list[dict] = []
        self.timeouts: list[float] = []

    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        self.queries.append(query)
        self.timeouts.append(timeout_seconds)
        if query["@type"] == "addProxy":
            return {"@type": "proxy", "id": 42}
        return {"@type": "ok"}


class MissingIdProxyClient(FakeProxyClient):
    def send_query(self, query: dict, timeout_seconds: float) -> dict:
        self.queries.append(query)
        if query["@type"] == "addProxy":
            return {"@type": "ok"}
        return {"@type": "ok"}


def test_tdlib_proxy_apply_uses_tdlib_proxy_methods(monkeypatch) -> None:
    logged_metadata: list[dict] = []

    def fake_log(account_id: str, **kwargs):
        logged_metadata.append(kwargs["proxy"])

    monkeypatch.setattr("app.services.tdlib_proxy._log_proxy_apply", fake_log)
    client = FakeProxyClient()

    applied = apply_account_proxy_to_tdlib(
        client,
        "account-1",
        config=Settings(tdlib_receive_timeout_seconds=0.01, tdlib_proxy_apply_timeout_seconds=7.0),
        proxy_settings=TdlibProxySettings(
            proxy_type="socks5",
            host="127.0.0.1",
            port=1080,
            username="user",
            password="secret",
        ),
    )

    assert applied is True
    assert [query["@type"] for query in client.queries] == ["addProxy", "enableProxy"]
    assert client.queries[0]["type"] == {
        "@type": "proxyTypeSocks5",
        "username": "user",
        "password": "secret",
    }
    assert all(proxy.password == "secret" for proxy in logged_metadata)
    assert client.timeouts == [7.0, 7.0]


def test_tdlib_proxy_apply_fails_when_add_proxy_returns_no_id(monkeypatch) -> None:
    monkeypatch.setattr("app.services.tdlib_proxy._log_proxy_apply", lambda *args, **kwargs: None)
    client = MissingIdProxyClient()

    try:
        apply_account_proxy_to_tdlib(
            client,
            "account-1",
            proxy_settings=TdlibProxySettings(proxy_type="http", host="127.0.0.1", port=8080),
        )
    except RuntimeError as exc:
        message = str(exc)
    else:
        message = ""

    assert message == "TDLib addProxy did not return proxy id"
    assert [query["@type"] for query in client.queries] == ["addProxy"]


def test_tdlib_proxy_apply_returns_false_when_account_has_no_proxy(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.tdlib_proxy.resolve_tdlib_proxy_settings", lambda account_id, config: None
    )

    assert apply_account_proxy_to_tdlib(FakeProxyClient(), "account-1") is False
