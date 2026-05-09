from __future__ import annotations

from app.observability import capture_observability_test_exception, init_worker_observability


def main() -> None:
    initialized = init_worker_observability()
    if not initialized:
        raise SystemExit("Worker observability is not configured or sentry-sdk is unavailable")
    captured = capture_observability_test_exception("StylistTG worker observability test error")
    if not captured:
        raise SystemExit("Worker observability test error was not captured")


if __name__ == "__main__":
    main()
