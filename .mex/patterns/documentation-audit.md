---
name: documentation audit
description: Keep docs, handoff, and memory aligned with code.
triggers:
  - documentation
  - audit
  - handoff
  - README
edges:
  - .mex/context/architecture.md
  - .mex/context/setup.md
  - .mex/patterns/mex-memory-update.md
last_updated: 2026-05-10
---

# Documentation Audit

## Context

Load `.mex/ROUTER.md`, `.mex/context/setup.md`, `.mex/context/workers.md`, and task-specific context. Check `AGENTS.md`, `.mex/`, `README.md`, `AGENT_HANDOFF.md`, and relevant files under `docs/`.

## Steps

1. Identify authoritative code paths before editing docs.
2. Update docs surgically; do not rewrite large sections without need.
3. Preserve the `8002` local dashboard vs `8000` live-validation distinction.
4. Keep warmup queue taxonomy in sync with `backend/app/services/worker_plane.py`.
5. Update `.mex` memory only when stable project knowledge changed.

## Verify

```powershell
git diff --check
```

Run tracked markdown link checks when links changed. Use grep/search for old terms such as stale ports, route names, or removed paths.

## Gotchas

- Do not edit `.env` files unless explicitly allowed.
- Do not read `.env.cloud.example` unless explicitly allowed.
- Do not delete files without explicit confirmation.
