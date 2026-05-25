"""Migration replay orchestrator for Task 46 (F-E002, F-E003, F-E006).

Drives alembic upgrade and downgrade against a disposable Postgres instance
and records per-revision timing. Uses the alembic *programmatic* API so each
revision step is timed without paying a fresh Python startup cost per call.

Usage::

    # Time every upgrade step from base → head.
    DATABASE_URL=postgresql+psycopg://replay:replay@localhost:15432/replay \\
        python -m scripts.migration_replay --direction upgrade \\
        --output replay-upgrade.json

    # Or a full roundtrip (head → base → head).
    DATABASE_URL=postgresql+psycopg://replay:replay@localhost:15432/replay \\
        python -m scripts.migration_replay --direction roundtrip \\
        --output replay-roundtrip.json

    # Re-render the JSON timings as the audit log Markdown.
    python -m scripts.migration_replay --format-as-markdown \\
        --input replay-roundtrip.json \\
        --output docs/audits/2026-05-safety-pipeline-audit/11-migration-replay-log.md
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _config() -> Config:
    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    return cfg


def _revisions(cfg: Config) -> list[str]:
    """Return revision IDs oldest → newest."""
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    return [rev.revision for rev in reversed(revisions)]


def _step(cfg: Config, direction: str, target: str) -> float:
    start = time.monotonic()
    if direction == "upgrade":
        command.upgrade(cfg, target)
    elif direction == "downgrade":
        command.downgrade(cfg, target)
    else:  # pragma: no cover - defensive
        raise ValueError(f"unknown direction: {direction}")
    return (time.monotonic() - start) * 1000


def _sweep(cfg: Config, direction: str) -> list[dict[str, Any]]:
    revisions = _revisions(cfg)
    if direction == "downgrade":
        # Walk from head → base. Use "-1" so each step moves one revision down
        # regardless of where the snapshot currently sits.
        rows: list[dict[str, Any]] = []
        for _ in range(len(revisions)):
            elapsed = _step(cfg, "downgrade", "-1")
            rows.append(
                {"revision": "-1", "direction": "downgrade", "elapsed_ms": round(elapsed, 1)}
            )
        # Append a final base label so the dataset is self-describing.
        rows.append({"revision": "base", "direction": "downgrade-complete", "elapsed_ms": 0.0})
        return rows

    # upgrade — walk base → head one revision at a time.
    rows = []
    for rev in revisions:
        elapsed = _step(cfg, "upgrade", rev)
        rows.append({"revision": rev, "direction": "upgrade", "elapsed_ms": round(elapsed, 1)})
    return rows


def _format_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Migration Replay Log")
    lines.append("")
    lines.append(
        "Replay executed via `scripts/migration_replay.py` "
        f"(direction: {payload.get('direction')})."
    )
    lines.append("")
    lines.append("| Migration | Direction | Elapsed (ms) |")
    lines.append("| --- | --- | ---: |")

    timings: list[float] = []
    for row in payload.get("rows", []):
        elapsed = row.get("elapsed_ms")
        if isinstance(elapsed, (int, float)) and elapsed > 0:
            timings.append(elapsed)
        lines.append(f"| `{row.get('revision')}` | {row.get('direction')} | {elapsed} |")

    if timings:
        p95 = (
            round(statistics.quantiles(timings, n=20)[-1], 1)
            if len(timings) >= 20
            else round(max(timings), 1)
        )
        lines.extend(
            [
                "",
                "## Aggregate",
                "",
                f"- total: **{round(sum(timings), 1)} ms**",
                f"- p95: **{p95} ms**",
                f"- max: **{round(max(timings), 1)} ms**",
                f"- count: **{len(timings)}**",
                "",
                "Per-migration timings include the alembic in-process step cost"
                " (~1–5 ms). For migrations whose DDL exceeds ~50 ms, the"
                " elapsed cost is dominated by the schema change itself.",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direction", choices=("upgrade", "downgrade", "roundtrip"))
    parser.add_argument("--output", help="Where to write the result.")
    parser.add_argument(
        "--format-as-markdown",
        action="store_true",
        help="Re-render an existing JSON timings file as the audit log Markdown.",
    )
    parser.add_argument("--input", help="Input JSON for --format-as-markdown.")
    args = parser.parse_args()

    if args.format_as_markdown:
        if not args.input or not args.output:
            raise SystemExit("--format-as-markdown requires --input and --output")
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        Path(args.output).write_text(_format_markdown(payload), encoding="utf-8")
        return

    if not args.direction or not args.output:
        raise SystemExit("--direction and --output are required when running a sweep")

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is required")

    cfg = _config()
    rows: list[dict[str, Any]] = []
    if args.direction in ("upgrade", "roundtrip"):
        rows.extend(_sweep(cfg, "upgrade"))
    if args.direction in ("downgrade", "roundtrip"):
        rows.extend(_sweep(cfg, "downgrade"))
        if args.direction == "roundtrip":
            rows.extend(_sweep(cfg, "upgrade"))

    payload = {
        "direction": args.direction,
        "rows": rows,
        "database_url_safe": os.environ.get("DATABASE_URL", "").split("@")[-1],
    }
    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} timings to {args.output}")


if __name__ == "__main__":
    main()
