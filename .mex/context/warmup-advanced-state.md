---
name: warmup-advanced-state
summary: Current implementation/planning status for Advanced Warmup work.
last_updated: 2026-06-08
edges:
  - .mex/context/warmup.md
  - .mex/patterns/warmup-advanced.md
  - docs/design/warmup-advanced-file-map.md
---

# Advanced Warmup State

## Purpose

Separate milestone state from procedural rules. Use `.mex/patterns/warmup-advanced.md` for how to work on advanced warmup and this file for what is implemented, planned, or blocked.

## Current State

- Account Preparation / Warmup foundation exists at backend `/api/warmup` and frontend `/modules/warmup`.
- Dry-run warmup sessions use `warmup_jobs`.
- Dispatch modes use `warmup_dispatch_jobs`; `shadow` is simulation-only.
- Live warmup remains gated by `WARMUP_LIVE_ENABLED`, mode-specific flags, TDLib runtime readiness, account isolation, and operator approval.
- Workspace Safety Policy is temporarily neutralized; check `.mex/status/current.md` before assuming behavioral policy fields are active.

## Planned Advanced Behavior

Advanced warmup should land only as a gated, staged expansion around per-account behavior:

- personality seed;
- channel-state selector;
- circadian windows;
- action-level pacing;
- stateful session/event/task-run records;
- explicit live-mode gates.

## Forbidden Claims

- Do not describe warmup as anti-ban, restriction bypass, shadow-ban protection, behavior imitation, or a Telegram safety guarantee.
- Do not imply advanced warmup is live-ready unless the current code, flags, TDLib readiness, and operator approval all support it.

## References

- `.mex/context/warmup.md`
- `.mex/patterns/warmup-change.md`
- `.mex/patterns/warmup-advanced.md`
- `docs/runbooks/account-preparation.md`
- `docs/design/warmup-advanced-file-map.md`
