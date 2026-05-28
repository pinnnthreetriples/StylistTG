---
name: worker queue change
description: Workflow for queue taxonomy, Redis/RQ worker, and scheduler changes.
triggers:
  - queue
  - worker
  - Redis
  - RQ
edges:
  - .mex/context/workers.md
  - .mex/context/backend.md
  - docs/runbooks/workers-production-plane.md
last_updated: 2026-05-28
---

# Worker Queue Change

## Context

Load `.mex/context/workers.md`. Check `backend/app/services/worker_plane.py`, `backend/app/job_queue/rq.py`, worker modules, and runbooks.

## Steps

1. Update queue allowlists and descriptors together.
2. Update enqueue helpers and worker entrypoints together.
3. Keep worker diagnostics aligned with production taxonomy.
4. Update README/runbooks and `.mex/context/workers.md`.
5. Add targeted backend tests for queue behavior.

## Verify

```powershell
cd backend; python -m pytest tests/test_worker_plane.py -q
cd backend; python -m ruff check .
```

Use actual test filenames if the touched queue has more specific tests.
