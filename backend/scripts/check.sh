#!/usr/bin/env bash
# Local quality gate wrapper (bash). Mirrors scripts/check.ps1 for *nix shells.
#
# Usage:
#   scripts/check.sh           # full gate
#   scripts/check.sh --fast    # skip slow checks
set -euo pipefail
cd "$(dirname "$0")/.."
exec python scripts/check.py "$@"
