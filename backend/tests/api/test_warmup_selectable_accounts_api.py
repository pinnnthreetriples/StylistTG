from __future__ import annotations

from app.models import AccountProxy
from tests.helpers.factories import seed_account


def test_warmup_selectable_accounts_filters_country_and_proxy(app_client, db_session) -> None:
    ca_account = seed_account(db_session, external_ref="+15550101000")
    co_account = seed_account(db_session, external_ref="+573001112233")
    ca_account.profile_state = None
    co_account.profile_state = None
    ca_account.account_state = "execution_usable"
    co_account.account_state = "execution_usable"
    db_session.add(
        AccountProxy(
            account_id=ca_account.id,
            proxy_type="socks5",
            proxy_category="residential",
            host="127.0.0.1",
            port=1080,
            status="ok",
        )
    )
    db_session.add(
        AccountProxy(
            account_id=co_account.id,
            proxy_type="socks5",
            proxy_category="datacenter",
            host="127.0.0.2",
            port=1080,
            status="failed",
            last_error_code="proxy_failed",
        )
    )
    db_session.commit()

    response = app_client.get("/api/warmup-selectable-accounts?country=CA&proxy_ok_only=true")

    assert response.status_code == 200
    payload = response.json()
    assert [item["account_id"] for item in payload] == [ca_account.id]
    assert payload[0]["country_iso"] == "CA"
    assert payload[0]["proxy_badge"] == "ok"


def test_warmup_selectable_accounts_searches_phone_and_caps_limit(app_client, db_session) -> None:
    account = seed_account(db_session, external_ref="+15550109999", origin="bought")

    response = app_client.get("/api/warmup-selectable-accounts?search=9999&limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["account_id"] == account.id
    assert payload[0]["role"] == "bought"
