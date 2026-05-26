from __future__ import annotations

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def _testcase_time(testcase: ET.Element) -> float:
    try:
        return float(testcase.attrib.get("time", "0"))
    except ValueError:
        return 0.0


def summarize(junit_xml: Path, output: Path, *, top: int) -> int:
    tree = ET.parse(junit_xml)
    root = tree.getroot()
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    if suite is None:
        raise ValueError(f"no testsuite found in {junit_xml}")

    testcases = list(suite.iter("testcase"))
    failures = [
        testcase
        for testcase in testcases
        if testcase.find("failure") is not None or testcase.find("error") is not None
    ]
    slowest = sorted(testcases, key=_testcase_time, reverse=True)[:top]

    lines = [
        f"tests={suite.attrib.get('tests', len(testcases))}",
        f"failures={suite.attrib.get('failures', len(failures))}",
        f"errors={suite.attrib.get('errors', '0')}",
        f"skipped={suite.attrib.get('skipped', '0')}",
        f"suite_seconds={suite.attrib.get('time', '0')}",
        "",
        f"top_{top}_slowest:",
    ]
    lines.extend(
        f"{_testcase_time(testcase):.3f}s {testcase.attrib.get('name', '<unnamed>')}"
        for testcase in slowest
    )
    if failures:
        lines.extend(["", "failures:"])
        lines.extend(testcase.attrib.get("name", "<unnamed>") for testcase in failures)

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return len(failures)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Schemathesis JUnit output.")
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()
    summarize(args.junit, args.output, top=args.top)


if __name__ == "__main__":
    main()
