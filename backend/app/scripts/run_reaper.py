from __future__ import annotations

import argparse
import json

from app.db import SessionLocal
from app.services.production_reaper import run_reaper_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run production reaper foundation in safe modes.")
    parser.add_argument("--mode", choices=["dry_run", "report_only", "execute_safe"], default="dry_run")
    args = parser.parse_args()
    with SessionLocal() as session:
        report = run_reaper_report(session, mode=args.mode)
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == "__main__":
    main()
