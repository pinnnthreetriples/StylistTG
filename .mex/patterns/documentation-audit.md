---
name: documentation audit
description: Keep docs, archived handoff, and mex memory aligned with code.
triggers:
  - documentation
  - audit
  - handoff
  - README
  - docs
edges:
  - .mex/ROUTER.md
  - .mex/status/current.md
  - .mex/context/architecture.md
  - .mex/context/decisions.md
  - .mex/context/setup.md
  - .mex/context/workers.md
  - .mex/patterns/mex-memory-update.md
  - .mex/patterns/architecture-change.md
  - docs/architecture/AGENT_ARCHITECTURE_GUIDE.md
last_updated: 2026-06-09
---

# Documentation Audit

## Context

Load:

1. `.mex/ROUTER.md`
2. `.mex/status/current.md`
3. task-specific `.mex/context/` files
4. `.mex/context/decisions.md` for durable decision history
5. relevant files under `docs/`

Root `AGENT_HANDOFF.md` is a compatibility pointer, not current documentation. Use `docs/archive/agent-handoff-2026-05.md` only as historical fallback when `.mex` and current docs do not answer the question.

For architecture or new-module documentation, also load `.mex/patterns/architecture-change.md` and `docs/architecture/AGENT_ARCHITECTURE_GUIDE.md`.

## Steps

1. Identify authoritative code paths before editing docs.
2. Identify the current source of truth: code, generated architecture artifact, runbook, `.mex/context/`, or decision log.
3. Update docs surgically; do not rewrite large sections without need.
4. Preserve the `8002` local dashboard vs `8000` live-validation distinction.
5. Keep queue taxonomy in sync with `backend/app/contracts/queues.py`, `backend/app/services/worker_plane.py`, and `backend/app/runtime/roles.py`.
6. Keep architecture guidance in sync with `docs/architecture/STRUCTURE_AUDIT.md` and `docs/quality/DEVELOPER_WORKFLOW.md`.
7. Update `.mex` memory only when stable project knowledge changed.

## Verify

```powershell
git diff --check
npm run memory:check
npm run memory:sync:dry-run
```

Run tracked markdown link checks when links changed. Use grep/search for old terms such as stale ports, route names, removed paths, `AGENT_HANDOFF.md` as canonical source, or legacy wrapper ownership language.

## Gotchas

- Do not edit `.env` files unless explicitly allowed.
- Do not read cloud env files, TDLib sessions, logs, or artifacts unless explicitly allowed.
- Do not delete files without explicit confirmation.
- Do not use archived handoff content as current architecture authority.
