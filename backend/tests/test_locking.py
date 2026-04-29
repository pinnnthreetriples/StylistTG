from app.services.accounts import create_account
from app.services.locks import acquire_account_lock


def test_account_lock_acquisition_rejects_stale_session_after_competing_owner(db_session) -> None:
    account = create_account(db_session, external_ref="primary")
    account_id = account.id

    first_epoch = acquire_account_lock(db_session, account_id, "worker-1")
    second_epoch = acquire_account_lock(db_session, account_id, "worker-2")

    assert first_epoch == 1
    assert second_epoch is None
