from __future__ import annotations

import ctypes
import os


def main() -> int:
    library_path = os.environ.get("TDLIB_SHARED_LIBRARY_PATH")
    if not library_path:
        print("TDLIB_SHARED_LIBRARY_PATH is not configured")
        return 1
    try:
        library = ctypes.CDLL(library_path)
    except OSError as exc:
        print(f"tdjson library is not loadable: {exc.__class__.__name__}")
        return 1
    missing = [
        symbol
        for symbol in (
            "td_json_client_create",
            "td_json_client_send",
            "td_json_client_receive",
            "td_json_client_destroy",
        )
        if not hasattr(library, symbol)
    ]
    if missing:
        print("tdjson library is missing symbols: " + ", ".join(missing))
        return 1
    print("tdjson runtime is loadable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
