# Git workflow without branch protection

This private repository currently cannot enforce GitHub branch protection or
rulesets on the active GitHub plan. Until GitHub Pro is enabled or the
repository becomes public, follow this workflow manually for every change.

## Mandatory workflow

1. Never work directly in `main`.
2. Start every task from an up-to-date `main`.

   ```powershell
   git checkout main
   git pull origin main
   git checkout -b codex/<task-name>
   ```

3. Put every change set through a draft pull request.
4. Before moving a PR to ready-for-review, verify:
   - `Backend` check passed.
   - `Frontend` check passed.
   - `git status` is clean.
   - No live Telegram/TDLib actions were run unless explicitly requested.
5. Merge only with squash merge.
6. After merge, update and verify local `main`.

   ```powershell
   git checkout main
   git pull origin main

   cd backend
   python -m alembic heads
   python -m ruff check .
   python -m pytest
   ```

## Prohibited actions

- Do not force push `main`.
- Do not push directly to `main`.
- Do not merge a failed PR.
- Do not bypass failed checks.
- Do not enable `AUTH_MODE=local` in production or cloud mode.

## Required checks

The GitHub Actions workflow currently exposes these check names:

- `Backend`
- `Frontend`

Treat both as required before merge, even though GitHub cannot enforce that on
the current private repository plan.
