from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 100.0
    return (numerator / denominator) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", default="mutants/mutmut-cicd-stats.json")
    parser.add_argument("--min-score", type=float, required=True)
    parser.add_argument("--max-unstable", type=int, default=0)
    args = parser.parse_args()

    stats_path = Path(args.stats)
    if not stats_path.exists():
        print(f"ERROR: mutation stats not found: {stats_path}", file=sys.stderr)
        return 2

    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    total = int(stats.get("total", 0))
    skipped = int(stats.get("skipped", 0))
    killed = int(stats.get("killed", 0))
    caught_by_type_check = int(stats.get("caught_by_type_check", 0))
    survived = int(stats.get("survived", 0))
    no_tests = int(stats.get("no_tests", 0))
    timeout = int(stats.get("timeout", 0))
    suspicious = int(stats.get("suspicious", 0))
    segfault = int(stats.get("segfault", 0))
    interrupted = int(stats.get("check_was_interrupted_by_user", 0))

    denominator = total - skipped
    passed = killed + caught_by_type_check
    score = _pct(passed, denominator)
    unstable = timeout + suspicious + segfault + interrupted

    print(f"mutation score: {score:.1f}% ({passed}/{denominator})")
    print(
        "mutants: "
        f"total={total} killed={killed} typecheck={caught_by_type_check} "
        f"survived={survived} no_tests={no_tests} skipped={skipped} unstable={unstable}"
    )

    failures: list[str] = []
    if total <= 0:
        failures.append("no mutants were checked")
    if score < args.min_score:
        failures.append(f"score {score:.1f}% < {args.min_score:.1f}%")
    if unstable > args.max_unstable:
        failures.append(f"unstable mutants {unstable} > {args.max_unstable}")

    if failures:
        print("FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("Mutation threshold met.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
