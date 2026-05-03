from __future__ import annotations

import argparse
import json
import sys

from app.config import settings
from app.services.tdlib_runtime import detect_tdlib_runtime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe TDLib runtime smoke check")
    parser.add_argument("--runtime-check", action="store_true", help="check TDLib runtime configuration")
    parser.add_argument("--library-check", action="store_true", help="check tdjson loadability")
    parser.add_argument("--readonly-auth-check", action="store_true", help="reserved explicit live readonly auth check")
    args = parser.parse_args(argv)

    status = detect_tdlib_runtime(settings)
    payload = status.to_safe_dict()
    if args.readonly_auth_check and not (settings.tdlib_live_enabled and settings.tdlib_readonly_smoke_enabled):
        payload["readonly_auth_check"] = "disabled"
    elif args.readonly_auth_check:
        payload["readonly_auth_check"] = "not_implemented_without_existing_auth_session"
    payload["status"] = "PASS" if (not args.library_check or not status.library_configured or status.library_loadable) else "FAIL"
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
