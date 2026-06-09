---
name: pattern index
description: Lookup table for repeatable StylistTG task workflows.
edges:
  - .mex/ROUTER.md
  - .mex/context/conventions.md
  - .mex/context/warmup-advanced-state.md
  - .mex/patterns/architecture-change.md
  - docs/architecture/AGENT_ARCHITECTURE_GUIDE.md
  - docs/design/warmup-advanced-file-map.md
last_updated: 2026-06-09
---

# Pattern Index

| Task | Pattern |
| --- | --- |
| Change architecture, module ownership, source-of-truth boundaries, or add a backend module | [architecture-change.md](architecture-change.md) |
| Audit or update project documentation/memory | [documentation-audit.md](documentation-audit.md) |
| Change backend API/service behavior | [backend-api-change.md](backend-api-change.md) |
| Change dashboard module/routes/UI | [frontend-module-change.md](frontend-module-change.md) |
| Change queue taxonomy, workers, scheduler, or Redis/RQ behavior | [worker-queue-change.md](worker-queue-change.md) |
| Change warmup/account-preparation behavior | [warmup-change.md](warmup-change.md) |
| Build Advanced Warmup v1 milestone work | [warmup-advanced.md](warmup-advanced.md) |
| Touch live TDLib/Telegram or sensitive runtime boundaries | [live-tdlib-safety.md](live-tdlib-safety.md) |
| Clean ignored/generated files | [safe-cleanup.md](safe-cleanup.md) |
| Update mex memory scaffold | [mex-memory-update.md](mex-memory-update.md) |
| Work with project board items | [board-workflow.md](board-workflow.md) |

If no pattern matches, follow `.mex/ROUTER.md` and create a compact pattern only after the task reveals a repeatable workflow.
