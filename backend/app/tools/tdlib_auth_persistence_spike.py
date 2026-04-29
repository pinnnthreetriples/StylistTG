from __future__ import annotations

import argparse

from app.adapters.tdlib_auth import TdlibAuthStatus, build_tdlib_auth_adapter, normalize_phone_number
from app.db import SessionLocal
from app.models import AccountState
from app.services.accounts import create_account, get_account_by_external_ref
from app.services.auth import confirm_otp, start_otp, submit_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual TDLib auth persistence spike.")
    parser.add_argument("--phone", required=True, help="Phone number in international format.")
    parser.add_argument("--code", help="Telegram OTP code for step 2.")
    parser.add_argument("--password", help="2FA password if step 2 returns wait_password.")
    args = parser.parse_args()
    phone = normalize_phone_number(args.phone)

    with SessionLocal() as session:
        account = get_account_by_external_ref(session, phone)
        if account is None:
            account = create_account(session, external_ref=phone)
        print(f"account_id={account.id}")

        if not args.code:
            result = start_otp(session, phone_number=phone, adapter=build_tdlib_auth_adapter())
            print(f"step=start_otp status={result.status} state={result.account.account_state} marker={result.runtime_state.recovery_marker}")
            if result.status != TdlibAuthStatus.WAIT_CODE:
                raise SystemExit("Gate failed: start_otp did not reach WAIT_CODE")
            print("Now run this command again with --code without deleting TDLib directories.")
            return

        result = confirm_otp(session, account_id=account.id, code=args.code, adapter=build_tdlib_auth_adapter())
        print(f"step=confirm_otp status={result.status} state={result.account.account_state} marker={result.runtime_state.recovery_marker}")
        if result.status == TdlibAuthStatus.WAIT_PASSWORD:
            if not args.password:
                print("TDLib restored auth state and now requires 2FA. Re-run with --password.")
                return
            result = submit_password(
                session,
                account_id=account.id,
                password=args.password,
                adapter=build_tdlib_auth_adapter(),
            )
            print(f"step=submit_password status={result.status} state={result.account.account_state}")
        if result.account.account_state not in {AccountState.AUTHORIZED_READY, AccountState.EXECUTION_USABLE}:
            raise SystemExit("Gate failed: confirm did not reach authorized/usable state")
        print("Gate passed: TDLib auth state survived client close and reopened by account_id.")


if __name__ == "__main__":
    main()
