---
name: safe cleanup
description: Cleanup workflow for ignored/generated files.
triggers:
  - cleanup
  - delete
  - git clean
edges:
  - .mex/context/security.md
  - .gitignore
last_updated: 2026-05-22
---

# Safe Cleanup

## Context

Use `git clean -ndX` only for dry-run discovery. Do not run blanket `git clean -fdX`.

## Safe disposable groups

- Dependency folders: `node_modules/`, workspace `node_modules/`, temporary audit venvs.
- Build artifacts: dist folders, Playwright reports, and test-results folders.
- Tool caches: turbo, ruff, pytest, and hypothesis cache folders.
- Python caches: pycache folders and egg-info metadata.

## Ask separately before deleting

- Logs.
- artifacts folders.
- Demo databases.

## Never delete without explicit approval

- Environment files.
- Dashboard local env files.
- Backend local env files.
- `backend/tdlib/`.
- Any local credentials, sessions, or production-like runtime data.
