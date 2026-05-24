---
name: warmup change
description: Workflow for account preparation/warmup updates.
triggers:
  - warmup
  - account preparation
  - WARMUP
edges:
  - .mex/context/warmup.md
  - .mex/context/security.md
  - .mex/patterns/worker-queue-change.md
last_updated: 2026-05-25
---

# Warmup Change

## Context

Load `.mex/context/warmup.md`, `.mex/context/security.md`, and `docs/runbooks/account-preparation.md`.

## Steps

1. Identify whether the change affects dry-run, shadow, passive, network, or advanced mode.
2. Keep live behavior gated and disabled by default.
3. Keep `warmup_session` as source of truth.
4. Sanitize `warmup_event.payload_json`.
5. Update backend, frontend, queue docs, and tests together when behavior changes.

## Verify

```powershell
cd backend; python -m pytest tests/test_warmup.py tests/test_warmup_worker.py -q
cd backend; python -m pytest tests/test_warmup_dispatch.py tests/test_warmup_passive.py tests/test_warmup_network_advanced.py tests/test_warmup_isolation.py -q
```

Do not enable live Telegram warmup for verification without explicit operator approval.
