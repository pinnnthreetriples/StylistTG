---
name: worker queue change
description: Workflow for queue taxonomy, Redis/RQ worker, scheduler, and runtime-role changes.
triggers:
  - queue
  - worker
  - Redis
  - RQ
  - runtime role
edges:
  - .mex/context/workers.md
  - .mex/context/backend.md
  - .mex/context/security.md
  - .mex/patterns/architecture-change.md
  - docs/architecture/production-execution-plane.md
  - docs/runbooks/workers-production-plane.md
last_updated: 2026-06-09
---

# Worker Queue Change

## Context

Load `.mex/context/workers.md`. Check these sources before editing:

- `backend/app/contracts/queues.py`
- `backend/app/services/worker_plane.py`
- `backend/app/runtime/roles.py`
- `backend/app/job_queue/rq.py`
- module enqueue helpers
- worker modules and runbooks

If the change affects queue taxonomy, runtime roles, workflow identifiers, or architecture boundaries, also use `.mex/patterns/architecture-change.md`.

## Steps

1. Update queue constants, allowlists, descriptors, and diagnostics together.
2. Update runtime roles when role-to-queue ownership changes.
3. Update enqueue helpers and worker entrypoints together.
4. Keep worker diagnostics aligned with production taxonomy.
5. Keep staging grouped-queue compatibility unless a task explicitly migrates it.
6. Update README/runbooks, `docs/architecture/production-execution-plane.md`, and `.mex/context/workers.md` when stable queue/role facts change.
7. Add targeted backend tests for queue behavior and role validation.

## Verify

```powershell
cd backend; python -m pytest tests/test_worker_plane.py -q
cd backend; python -m pytest tests/architecture -q
cd backend; python -m ruff check .
```

Use actual test filenames if the touched queue has more specific tests.
