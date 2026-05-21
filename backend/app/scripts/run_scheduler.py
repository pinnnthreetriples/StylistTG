from __future__ import annotations

import argparse
import json
import time

from app.services.scheduler import (
    RATE_LIMIT_FLUSH_TICK_SECONDS,
    enqueue_rate_limit_flush_tick,
    scheduler_report,
)


def _enqueue_once() -> dict[str, object]:
    return {
        "rate_limit_flush_enqueued": enqueue_rate_limit_flush_tick(),
        "report": scheduler_report().to_dict(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run safe scheduler enqueue ticks.")
    parser.add_argument("--once", action="store_true", help="enqueue one scheduler tick and exit")
    parser.add_argument("--loop", action="store_true", help="enqueue scheduler ticks forever")
    args = parser.parse_args(argv)

    if args.once:
        print(json.dumps(_enqueue_once(), indent=2))
        return

    if args.loop:
        while True:
            print(json.dumps(_enqueue_once(), indent=2))
            time.sleep(RATE_LIMIT_FLUSH_TICK_SECONDS)

    print(json.dumps(scheduler_report().to_dict(), indent=2))


if __name__ == "__main__":
    main()
