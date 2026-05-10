---
name: live tdlib safety
description: Safety checklist for live Telegram/TDLib-sensitive work.
triggers:
  - TDLib
  - Telegram
  - live
  - session
edges:
  - .mex/context/security.md
  - .mex/context/warmup.md
  - docs/runbooks/live-validation.md
last_updated: 2026-05-10
---

# Live TDLib Safety

## Context

Load `.mex/context/security.md` and relevant runbooks. Confirm whether the task is mock, dry-run, read-only live validation, or real live mutation.

## Rules

- Never run live TDLib calls against real Telegram accounts without explicit approval.
- Never inspect TDLib session directories unless explicitly approved.
- Never persist auth codes or 2FA passwords.
- Never expose raw TDLib paths or session values in diagnostics.
- Use read-only runtime smoke checks before any live operation.

## Verify

Use safe smoke checks only unless the user explicitly approves live behavior:

```powershell
cd backend; python -m app.scripts.tdlib_runtime_smoke --runtime-check --library-check
```
