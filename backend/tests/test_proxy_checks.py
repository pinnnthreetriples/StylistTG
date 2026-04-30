from app.config import Settings
from app.models import AccountProxy
from app.services.accounts import create_account
from app.services.proxy_checks import check_account_proxy


class OkTcpChecker:
    def check(self, proxy: AccountProxy):
        return True, None, None


class FailedTdlibChecker:
    def check_account(self, account_id: str) -> dict:
        return {
            "status": "runtime_broken",
            "runtime_health": "proxy_tdlib_failed",
            "error_code": "tdlib_proxy_check_failed",
        }


def test_proxy_check_runs_tdlib_readonly_check_in_tdlib_mode(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    db_session.add(
        AccountProxy(
            account_id=account.id,
            proxy_type="socks5",
            host="127.0.0.1",
            port=1080,
            status="unknown",
        )
    )
    db_session.commit()

    result = check_account_proxy(
        db_session,
        account.id,
        checker=OkTcpChecker(),
        tdlib_checker=FailedTdlibChecker(),
        config=Settings(profile_execution_adapter="tdlib", tdlib_api_id=1, tdlib_api_hash="hash"),
    )

    assert result["status"] == "failed"
    assert result["last_error_code"] == "tdlib_proxy_check_failed"
