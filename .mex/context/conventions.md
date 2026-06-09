---
name: conventions
description: Coding standards, verification habits, and project-specific rules.
triggers:
  - convention
  - review
  - verify
  - style
edges:
  - .mex/context/backend.md
  - .mex/context/frontend.md
  - .mex/context/security.md
last_updated: 2026-06-08
---

# Conventions

## General

- Prefer minimal surgical changes over broad rewrites.
- If ambiguity blocks safe execution, ask once. Otherwise state the assumption and proceed surgically.
- Do not change unrelated source files.
- Do not expand scope because related legacy context exists in `AGENT_HANDOFF.md` or archived handoff snapshots.
- Do not add live Telegram behavior without explicit approval.
- Keep memory updates compact and factual.

## Backend

- Python 3.14+ with type hints.
- Use module-owned services/facades/contracts for module behavior; keep legacy wrappers as compatibility surfaces.
- Keep route handlers thin.
- Preserve workspace scoping.
- Use pytest and ruff for verification.

## Frontend

- TypeScript strict.
- Functional React with hooks.
- Use package `@stylisttg/ui` for product UI primitives where possible.
- Keep dashboard UI clean, minimal, compact, and not visually bulky.
- Prefer typed API client helpers over ad hoc fetches.

## Verification

- For backend changes, run targeted pytest and `python -m ruff check .`.
- For frontend changes, run targeted vitest plus lint/typecheck when practical.
- For docs/memory changes, run `git diff --check` and `npm run memory:check` when paths, commands, routing, or memory scaffold changed.
