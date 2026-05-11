from app.config import Settings
from app.models import AccountOperationLog, AccountProxy
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


class ValidTdlibChecker:
    def check_account(self, account_id: str) -> dict:
        return {"status": "valid", "runtime_health": "ready"}


class ReauthTdlibChecker:
    def check_account(self, account_id: str) -> dict:
        return {"status": "reauth_required", "runtime_health": "awaiting_code", "error_code": "tdlib_wait_code"}


class FailedTcpChecker:
    def check(self, proxy: AccountProxy):
        return False, "proxy_timeout", "timeout"


def _seed_proxy(db_session) -> str:
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
    return account.id


def test_proxy_check_tcp_only_marks_tcp_working(db_session) -> None:
    account_id = _seed_proxy(db_session)

    result = check_account_proxy(db_session, account_id, checker=OkTcpChecker(), config=Settings(profile_execution_adapter="mock"))

    assert result["status"] == "tcp_working"
    assert result["last_check_scope"] == "tcp"
    assert result["last_error_code"] is None


def test_proxy_check_marks_tdlib_working_when_readonly_check_is_valid(db_session) -> None:
    account_id = _seed_proxy(db_session)

    result = check_account_proxy(
        db_session,
        account_id,
        checker=OkTcpChecker(),
        tdlib_checker=ValidTdlibChecker(),
        config=Settings(profile_execution_adapter="tdlib", tdlib_api_id=1, tdlib_api_hash="hash"),
    )

    assert result["status"] == "tdlib_working"
    assert result["last_check_scope"] == "tcp_tdlib"
    assert result["tdlib_verified_at"] is not None


def test_proxy_check_keeps_account_readiness_separate_from_proxy_failure(db_session) -> None:
    account_id = _seed_proxy(db_session)

    result = check_account_proxy(
        db_session,
        account_id,
        checker=OkTcpChecker(),
        tdlib_checker=ReauthTdlibChecker(),
        config=Settings(profile_execution_adapter="tdlib", tdlib_api_id=1, tdlib_api_hash="hash"),
    )

    assert result["status"] == "tdlib_unverified"
    assert result["last_error_code"] is None
    assert result["tdlib_last_error_code"] == "tdlib_wait_code"


def test_proxy_check_marks_tcp_failure_as_failed(db_session) -> None:
    account_id = _seed_proxy(db_session)

    result = check_account_proxy(db_session, account_id, checker=FailedTcpChecker())

    assert result["status"] == "failed"
    assert result["last_check_scope"] == "tcp"
    assert result["last_error_code"] == "proxy_timeout"


def test_proxy_check_marks_tdlib_runtime_failure_separately(db_session) -> None:
    account_id = _seed_proxy(db_session)

    result = check_account_proxy(
        db_session,
        account_id,
        checker=OkTcpChecker(),
        tdlib_checker=FailedTdlibChecker(),
        config=Settings(profile_execution_adapter="tdlib", tdlib_api_id=1, tdlib_api_hash="hash"),
    )

    assert result["status"] == "tdlib_failed"
    assert result["last_error_code"] is None
    assert result["tdlib_last_error_code"] == "tdlib_proxy_check_failed"
    log = db_session.query(AccountOperationLog).filter_by(operation_key="check_proxy").one()
    assert log.error_code == "tdlib_proxy_check_failed"
    assert log.error_class == "tdlib_proxy"
