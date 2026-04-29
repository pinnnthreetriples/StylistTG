from app.models import AccountState
from app.services.accounts import create_account
from app.services.execution_policy import ensure_execution_usable
from app.services.jobs import create_profile_job

from conftest import FakeExecutionUsableAdapter


def test_ensure_execution_usable_promotes_authorized_account(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = AccountState.AUTHORIZED_READY
    db_session.commit()

    result = ensure_execution_usable(db_session, account.id, adapter=FakeExecutionUsableAdapter())

    assert result.account.account_state == AccountState.EXECUTION_USABLE
    assert result.runtime_state.runtime_health == "ready"
    assert result.account.telegram_user_id == "123456"


def test_create_profile_job_blocks_non_execution_usable_account(db_session) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = AccountState.AUTHORIZED_READY
    db_session.commit()

    try:
        create_profile_job(
            db_session,
            account_id=account.id,
            payload={"name": "Stylist TG", "bio": None, "username": None, "photo_asset_id": None},
            execution_adapter=FakeExecutionUsableAdapter(ok=False),
        )
    except ValueError as exc:
        assert "execution_usable" in str(exc)
    else:
        raise AssertionError("job was created for non-usable account")


def test_create_profile_job_requires_valid_profile_photo_asset(db_session, storage_dir) -> None:
    account = create_account(db_session, external_ref="+15550102000")
    account.account_state = AccountState.EXECUTION_USABLE
    db_session.commit()

    try:
        create_profile_job(
            db_session,
            account_id=account.id,
            payload={
                "name": "Stylist TG",
                "bio": None,
                "username": None,
                "photo_asset_id": "missing-asset",
            },
            execution_adapter=FakeExecutionUsableAdapter(),
        )
    except ValueError as exc:
        assert "asset" in str(exc)
    else:
        raise AssertionError("job was created with missing asset")
