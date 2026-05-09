from __future__ import annotations

from app.observability import capture_observability_test_exception, init_api_observability


def main() -> None:
    initialized = init_api_observability()
    if not initialized:
        raise SystemExit("API observability is not configured or sentry-sdk is unavailable")
    captured = capture_observability_test_exception("StylistTG API observability test error")
    if not captured:
        raise SystemExit("API observability test error was not captured")


if __name__ == "__main__":
    main()
