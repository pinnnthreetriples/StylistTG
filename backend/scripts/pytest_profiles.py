"""Canonical pytest profile definitions (issue #264).

Single source of truth for the marker expressions used by GitHub Actions,
local ``scripts/check.py`` invocations, and developer documentation.

Importing this module gives both the raw marker expression and a
``--profile NAME`` CLI for shell consumption:

    uv run python -m scripts.pytest_profiles pr-markers
    uv run python -m scripts.pytest_profiles nightly-slow-property-markers

The exit code is always 0 unless an unknown profile is requested.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """A named pytest selection profile.

    ``marker_expr`` is fed to ``pytest -m``. ``paths`` are the pytest path
    arguments (typically ``tests`` or ``tests/contract``). Notes capture the
    intent so reviewers can audit drift between this module and the workflow
    YAML.
    """

    name: str
    marker_expr: str
    paths: tuple[str, ...]
    notes: str


# PR-required: fast, deterministic. Excludes every heavy marker.
PR = Profile(
    name="pr",
    marker_expr=(
        "not contract and not live and not integration and not postgres "
        "and not redis and not slow and not benchmark and not mutation "
        "and not property_heavy and not nightly"
    ),
    paths=("tests",),
    notes=(
        "Required PR profile. Excludes all heavy markers; includes unit/api/"
        "security/worker/storage/architecture/property_pr."
    ),
)

# Hard contract-security subset that runs alongside the PR profile.
CONTRACT_SECURITY = Profile(
    name="contract-security",
    marker_expr="contract and contract_security",
    paths=("tests/contract/security",),
    notes="Narrow security-sensitive contract subset. Runs in PR + nightly.",
)

# Nightly slow + heavy property tests.
NIGHTLY_SLOW_PROPERTY = Profile(
    name="nightly-slow-property",
    marker_expr="slow or property_heavy or nightly",
    paths=("tests",),
    notes=(
        "Nightly heavy profile. Runs slow/property_heavy/nightly markers. "
        "Hard-fails on any selected test failure."
    ),
)

# Nightly broad OpenAPI/Schemathesis contract fuzz.
NIGHTLY_CONTRACT = Profile(
    name="nightly-contract",
    marker_expr="contract",
    paths=("tests/contract",),
    notes=(
        "Nightly contract fuzz. SCHEMATHESIS_MAX_EXAMPLES set externally; "
        "100 in scheduled runs, 1-5 in PR/manual fast mode."
    ),
)

# Nightly Postgres/Redis service-container parity tests.
NIGHTLY_POSTGRES_REDIS = Profile(
    name="nightly-postgres-redis",
    marker_expr="postgres or redis or integration",
    paths=("tests",),
    notes="Service-container parity. Requires PG/Redis services in the runner.",
)

# Nightly mutation testing (driven by scripts/mutation_suite.py).
NIGHTLY_MUTATION = Profile(
    name="nightly-mutation",
    marker_expr="mutation",
    paths=("tests",),
    notes="Mutation-testing helpers; the real driver is scripts/mutation_suite.py.",
)

# Benchmark profile (manual or scheduled, never PR-required).
BENCHMARK = Profile(
    name="benchmark",
    marker_expr="benchmark",
    paths=("tests",),
    notes="Performance budgets. Disabled by default; benchmark workflows opt-in.",
)

# Live/operator-only tests (real TDLib/S3/staging).
LIVE = Profile(
    name="live",
    marker_expr="live",
    paths=("tests",),
    notes="Live environment smoke tests. Run only with explicit operator approval.",
)


ALL_PROFILES: dict[str, Profile] = {
    p.name: p
    for p in (
        PR,
        CONTRACT_SECURITY,
        NIGHTLY_SLOW_PROPERTY,
        NIGHTLY_CONTRACT,
        NIGHTLY_POSTGRES_REDIS,
        NIGHTLY_MUTATION,
        BENCHMARK,
        LIVE,
    )
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "field",
        choices=[
            *(f"{name}-markers" for name in ALL_PROFILES),
            *(f"{name}-paths" for name in ALL_PROFILES),
            "list",
        ],
        help="Which profile field to print. Use '<name>-markers' or '<name>-paths'.",
    )
    args = parser.parse_args(argv)

    if args.field == "list":
        for profile in ALL_PROFILES.values():
            print(f"{profile.name}\t{profile.marker_expr}")
        return 0

    suffix = "-markers" if args.field.endswith("-markers") else "-paths"
    name = args.field[: -len(suffix)]
    profile = ALL_PROFILES[name]
    if suffix == "-markers":
        print(profile.marker_expr)
    else:
        print(" ".join(profile.paths))
    return 0


if __name__ == "__main__":
    sys.exit(main())
