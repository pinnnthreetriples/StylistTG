---
name: pattern index
description: Lookup table for repeatable StylistTG task workflows.
edges:
  - .mex/ROUTER.md
  - .mex/context/conventions.md
last_updated: 2026-05-22
---

# Pattern Index

| Task | Pattern |
| --- | --- |
| Audit or update project documentation/memory | [documentation-audit.md](documentation-audit.md) |
| Change backend API/service behavior | [backend-api-change.md](backend-api-change.md) |
| Change dashboard module/routes/UI | [frontend-module-change.md](frontend-module-change.md) |
| Change queue taxonomy, workers, scheduler, or Redis/RQ behavior | [worker-queue-change.md](worker-queue-change.md) |
| Change warmup/account-preparation behavior | [warmup-change.md](warmup-change.md) |
| Touch live TDLib/Telegram or sensitive runtime boundaries | [live-tdlib-safety.md](live-tdlib-safety.md) |
| Clean ignored/generated files | [safe-cleanup.md](safe-cleanup.md) |
| Update mex memory scaffold | [mex-memory-update.md](mex-memory-update.md) |

If no pattern matches, follow `.mex/ROUTER.md` and create a compact pattern only after the task reveals a repeatable workflow.
