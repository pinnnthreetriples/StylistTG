from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_DURATION_RE = re.compile(
    r"^\s*(?P<duration>\d+(?:\.\d+)?)s\s+"
    r"(?P<phase>setup|call|teardown)\s+"
    r"(?P<nodeid>.+?)\s*$"
)


@dataclass(frozen=True)
class SlowTestEntry:
    nodeid: str
    phase: str
    duration_seconds: float


def parse_pytest_durations(log_text: str) -> list[SlowTestEntry]:
    entries: list[SlowTestEntry] = []
    for line in log_text.splitlines():
        match = _DURATION_RE.match(line)
        if not match:
            continue
        entries.append(
            SlowTestEntry(
                nodeid=match.group("nodeid"),
                phase=match.group("phase"),
                duration_seconds=float(match.group("duration")),
            )
        )
    return sorted(entries, key=lambda item: item.duration_seconds, reverse=True)


def build_report(
    entries: list[SlowTestEntry],
    thresholds: tuple[float, ...],
) -> dict[str, object]:
    return {
        "summary": {
            "reported_tests": len(entries),
            "thresholds_seconds": list(thresholds),
            "over_threshold": {
                str(threshold): sum(
                    1 for entry in entries if entry.duration_seconds > threshold
                )
                for threshold in thresholds
            },
        },
        "tests": [asdict(entry) for entry in entries],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a JSON report from pytest --durations output."
    )
    parser.add_argument("--log", required=True, help="Path to captured pytest stdout/stderr log")
    parser.add_argument("--output", required=True, help="Path to write slow-tests JSON report")
    parser.add_argument(
        "--threshold",
        dest="thresholds",
        action="append",
        type=float,
        default=[],
        help="Slow-test threshold in seconds. Can be repeated.",
    )
    args = parser.parse_args(argv)

    log_path = Path(args.log)
    output_path = Path(args.output)
    thresholds = tuple(args.thresholds or [3.0, 5.0, 10.0])

    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    report = build_report(parse_pytest_durations(log_text), thresholds)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
