"""Enforce a wall-clock budget for tests in the PR profile (issue #264).

Reads ``reports/slow-tests.json`` (produced by ``scripts/report_slow_tests.py``)
and fails non-zero if any unmarked test exceeded the call-phase or setup-phase
budget. Tests carrying any of the ``--allow-marked`` markers are exempt — they
are expected to be slow and live in nightly profiles.

Typical usage from CI:

    uv run python scripts/enforce_slow_test_budget.py \
        --report reports/slow-tests.json \
        --max-call-seconds 3 \
        --max-setup-seconds 2 \
        --allow-marked slow,integration,postgres,redis,benchmark,property_heavy \
        --profile pr
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"


_NODEID_RE = re.compile(r"^(?P<path>[^:]+)::(?P<name>.+)$")


def _markers_for_test(nodeid: str) -> set[str]:
    """Best-effort marker discovery without running pytest.

    Walks back from the test function definition to find ``@pytest.mark.X``
    decorators and module-level ``pytestmark = pytest.mark.X`` lines. False
    positives are acceptable here — over-marking an allow-listed test only
    weakens the budget for that test, not for the suite.
    """
    match = _NODEID_RE.match(nodeid)
    if not match:
        return set()
    path_str = match.group("path")
    test_name = match.group("name").split("[", 1)[0]

    file_path = REPO_ROOT / path_str
    if not file_path.is_file():
        return set()

    try:
        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set()

    markers: set[str] = set()
    pytestmark_re = re.compile(r"pytest\.mark\.(\w+)")
    decorator_re = re.compile(r"^\s*@pytest\.mark\.(\w+)")
    def_re = re.compile(rf"^\s*def\s+{re.escape(test_name)}\s*\(")

    # Module-level pytestmark assignments.
    for line in lines:
        if line.startswith("pytestmark") and "pytest.mark." in line:
            markers.update(pytestmark_re.findall(line))

    # Decorators directly above the function definition.
    for i, line in enumerate(lines):
        if not def_re.match(line):
            continue
        j = i - 1
        while j >= 0 and (
            lines[j].startswith(" ")
            or lines[j].startswith("\t")
            or lines[j].lstrip().startswith("@")
            or not lines[j].strip()
        ):
            stripped = lines[j].lstrip()
            if stripped.startswith("@"):
                m = decorator_re.match(lines[j])
                if m:
                    markers.add(m.group(1))
            elif stripped and not stripped.startswith("@") and not stripped.startswith("#"):
                break
            j -= 1
        break
    return markers


def _filter_unbudgeted(
    slow_entries: list[dict[str, object]],
    *,
    max_call: float,
    max_setup: float,
    allowed_markers: set[str],
) -> list[tuple[str, str, float]]:
    """Return ``(nodeid, phase, seconds)`` for every test that overran budget."""
    violations: list[tuple[str, str, float]] = []
    for entry in slow_entries:
        nodeid = str(entry.get("nodeid", ""))
        phase = str(entry.get("phase", "call"))
        # report_slow_tests.py emits SlowTestEntry.duration_seconds; older
        # synthetic inputs used the unqualified `seconds` key — accept both
        # so the gate stays honest when the producer schema evolves.
        raw_seconds = entry.get("duration_seconds", entry.get("seconds", 0.0))
        seconds = float(raw_seconds or 0.0)

        budget = max_call if phase == "call" else max_setup if phase == "setup" else None
        if budget is None or seconds <= budget:
            continue

        markers = _markers_for_test(nodeid)
        if markers & allowed_markers:
            continue
        violations.append((nodeid, phase, seconds))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", default="reports/slow-tests.json")
    parser.add_argument("--max-call-seconds", type=float, default=3.0)
    parser.add_argument("--max-setup-seconds", type=float, default=2.0)
    parser.add_argument(
        "--allow-marked",
        # `architecture` exempts the structure-audit drift tests in
        # tests/architecture/. Each spawns a subprocess to regenerate the
        # audit (~40-80s each) by design and must run on every PR to catch
        # docs/architecture/* drift — they cannot be moved to `slow` without
        # losing that signal.
        default=(
            "slow,integration,postgres,redis,benchmark,property_heavy,"
            "nightly,live,architecture"
        ),
        help="Comma-separated markers that exempt a test from the budget.",
    )
    parser.add_argument(
        "--profile",
        default="pr",
        help="Profile name used in failure messages.",
    )
    parser.add_argument(
        "--require-report",
        action="store_true",
        help=(
            "Fail with exit 2 when the slow-test report is missing. Required in CI "
            "(set in .github/workflows/test-quality.yml) so a broken report "
            "generator cannot silently disable the runtime-budget gate."
        ),
    )
    args = parser.parse_args(argv)

    report_path = REPO_ROOT / args.report
    if not report_path.is_file():
        if args.require_report:
            print(
                f"slow-test report missing at {report_path}; --require-report set, "
                f"failing the budget gate (exit 2). Generate the report with "
                f"`scripts/report_slow_tests.py` before invoking this script.",
                file=sys.stderr,
            )
            return 2
        # Local/manual invocation without a report — emit a clear signal but
        # do not fail.
        print(f"slow-test report not found at {report_path}, skipping budget check.")
        return 0

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    # ``report_slow_tests.py`` writes either a flat list or {"entries": [...]}.
    entries: Iterable[dict[str, object]]
    if isinstance(payload, dict):
        entries = payload.get("entries") or payload.get("tests") or []
    else:
        entries = payload  # type: ignore[assignment]

    allowed = {m.strip() for m in args.allow_marked.split(",") if m.strip()}

    violations = _filter_unbudgeted(
        list(entries),
        max_call=args.max_call_seconds,
        max_setup=args.max_setup_seconds,
        allowed_markers=allowed,
    )

    if not violations:
        print(
            f"slow-test budget OK ({args.profile}): no unmarked test exceeded "
            f"call={args.max_call_seconds}s / setup={args.max_setup_seconds}s."
        )
        return 0

    print(
        f"slow-test budget VIOLATED ({args.profile}): {len(violations)} unmarked "
        f"test(s) exceeded the budget. Either speed them up or add one of: "
        f"{sorted(allowed)}.",
        file=sys.stderr,
    )
    for nodeid, phase, seconds in violations:
        print(f"  {nodeid}  [{phase}={seconds:.2f}s]", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
