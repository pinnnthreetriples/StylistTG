---
name: StylistTG agent anchor
description: Canonical mex source anchor. Keep root AGENTS.md in sync.
last_updated: 2026-05-10
---

# StylistTG

Telegram account/profile automation platform: React/TS/Vite monorepo + FastAPI + RQ/Redis + TDLib.

## Non-Negotiables

- Read `.mex/ROUTER.md` before non-trivial work.
- Never read, commit, or copy secrets/runtime data; `.env*`, `backend/tdlib/`, logs, and artifacts are local-only unless explicitly approved.
- Do not run live TDLib/Telegram calls or live warmup behavior without explicit operator approval.
- Ask before `npm install`, `pip install`, file deletion, git push, or production-like operations.
- Make minimal, surgical changes and verify with targeted checks.
- Use package @stylisttg/ui for dashboard product UI when an equivalent exists.

## Core Commands

```powershell
.\scripts\start-dev.ps1
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
cd backend; python -m pytest -q
cd backend; python -m ruff check .
```

## Memory Commands

- Run `npm run memory:check` after memory/docs/scaffold changes or when commands, paths, ports, routes, queues, feature flags, or architecture change.
- Do not run `npm run memory:check` after every small code edit, test-only change, typo, local debug step, or purely visual tweak.
- Prefer `npm run memory:sync:dry-run`; do not run `npm run memory:sync` without explicit user approval.

## Memory

- `.mex/AGENTS.md` is the mex source anchor; root `AGENTS.md` is the tool-facing copy.
- `.mex/ROUTER.md` is the structured memory router and should be read first.
- `AGENT_HANDOFF.md` is retained as a legacy/full handoff snapshot during migration.
- Detailed docs remain in `docs/` and specs remain in `specs/`.
