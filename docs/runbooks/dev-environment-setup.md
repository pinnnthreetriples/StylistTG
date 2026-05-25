# Dev environment setup

Closes audit Phase 0 baseline gap (F-041): contributors must have a local
environment that can collect the full backend test suite and run security
scans without missing dependencies.

## Prerequisites

- **Python 3.12** (matches `backend/pyproject.toml requires-python`).
- **Node.js 20+** with npm 11.
- **Git**, **PowerShell 7+** (Windows) or **bash** (macOS/Linux).
- **Docker Desktop** (optional, required for `migration_replay` against a
  disposable Postgres — see `docs/runbooks/migration-safety.md`).

## Backend Python deps

The canonical install uses `uv` (matches CI). For local exploration, plain
`pip` also works because `pyproject.toml` is the source of truth.

```powershell
# uv-managed (recommended; matches CI lockfile)
cd backend
python -m pip install uv==0.10.9
uv sync --locked --extra dev

# or, plain pip with editable install
cd backend
pip install -e .
pip install -e .[dev]
```

The `[dev]` extra now installs `bandit`, `pip-audit`, `fakeredis`, `faker`,
and `vulture` alongside the existing test/typecheck/lint stack.
`prometheus_client` is already a main runtime dependency.

Verify the install:

```powershell
python -c "import prometheus_client, bandit, pip_audit, fakeredis, faker, vulture; print('ok')"
```

## Node deps

```powershell
npm install
```

This installs `markdownlint-cli` and the rest of the workspace tooling.
Verify:

```powershell
npx markdownlint-cli --version
```

## System tools

### Windows

```powershell
# semgrep (Python tool that lives in the same venv as the backend)
pip install semgrep>=1.50

# jq
winget install jqlang.jq

# Docker Desktop (for disposable Postgres replay)
winget install Docker.DockerDesktop
```

### macOS

```bash
brew install semgrep jq
brew install --cask docker
```

### Linux (Debian/Ubuntu)

```bash
sudo apt-get install -y jq
pip install semgrep>=1.50
# Docker: follow https://docs.docker.com/engine/install/ubuntu/
```

## Verifying the local environment

```powershell
# Backend collection (Phase 0 baseline blocker — must pass)
cd backend
python -m pytest tests --ignore=tests/contract --ignore=tests/benchmarks --collect-only -q | tail -3

# Security scans (non-blocking locally; CI promotes them gradually)
python -m bandit -r app -ll
python -m pip_audit --skip-editable --progress-spinner=off

# Markdown lint (root)
cd ..
npx markdownlint-cli "docs/**/*.md" "README.md" || true
```

If `pytest --collect-only` reports import errors for `prometheus_client`,
re-run `pip install -e backend` or `uv sync --extra dev` — the package was
promoted to a main runtime dependency in this PR. Tests tagged with the
`requires_metrics` or `requires_fakeredis` marker are auto-skipped (with an
actionable message) when the matching dependency is missing locally.

## CI parity

The PR pipeline already runs `pip-audit` in the `audit` job. Bandit was
added to the same job as a non-blocking step until existing findings are
either fixed or explicitly waivered. Promote `bandit` to a hard gate after
the cleanup pass.

## Troubleshooting

- `ModuleNotFoundError: prometheus_client` → run `pip install -e backend`
  (now a main dep, not optional).
- `ModuleNotFoundError: fakeredis` → install dev extras
  (`pip install -e backend[dev]`).
- `bandit: command not found` → install dev or security extras
  (`pip install -e backend[security]` for the lighter footprint).
- `docker: command not found` → install Docker Desktop or skip the
  migration replay flow; CI does not require Docker for the PR gates.
