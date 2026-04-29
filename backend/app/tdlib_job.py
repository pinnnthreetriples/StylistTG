from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.adapters.tdlib_profile_execution import build_profile_execution_adapter
from app.logging_utils import configure_logging


def main() -> int:
    configure_logging(log_dir="logs")
    parser = argparse.ArgumentParser(description="Run one TDLib profile job.")
    parser.add_argument("job_id")
    parser.add_argument("--plan-file", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
    adapter = build_profile_execution_adapter()
    failed = False
    uncertain = False
    try:
        for event in adapter.execute(
            payload["account_id"], payload["plan_json_snapshot"], payload["payload_json"]
        ):
            if event["event"] == "runtime_failed":
                failed = True
            if event["event"] == "step_uncertain":
                uncertain = True
            print(json.dumps({"job_id": args.job_id, **event}, sort_keys=True), flush=True)
    except SystemExit as exc:
        return int(exc.code)
    if failed:
        return 1
    if uncertain:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
