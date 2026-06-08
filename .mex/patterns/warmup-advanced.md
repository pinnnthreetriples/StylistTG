---
name: advanced warmup
description: Compact procedural rules for Advanced Warmup v1 implementation work.
edges:
  - .mex/ROUTER.md
  - .mex/context/warmup.md
  - .mex/context/warmup-advanced-state.md
  - .mex/patterns/warmup-change.md
  - docs/design/warmup-advanced-file-map.md
  - docs/runbooks/account-preparation.md
  - docs/design/warmup-ux-blueprint.md
  - docs/design/warmup-divergence-from-gramgpt.md
last_updated: 2026-06-08
---

# Advanced Warmup v1 Pattern

Use this compact pattern before Advanced Warmup v1 work. Current milestone state lives in `.mex/context/warmup-advanced-state.md`; large planned file maps and action catalogs live in `docs/design/warmup-advanced-file-map.md`.

## Architecture Rules

1. **One action handler pattern.** Each new TDLib action must have a real adapter handler, mock parity, and a registry/contract entry. Do not branch on `action_type` inside `dispatch_processor.py`.
2. **Strategy snapshot is sacred.** Session dispatch reads `WarmupSession.strategy_snapshot_json`; mutable `WarmupStrategy` rows are not the runtime source for in-flight sessions.
3. **Event log first.** Scheduler, selector, lifecycle, safety, and action decisions write sanitized `warmup_event` entries.
4. **Mock parity.** Every real action has deterministic mock behavior so `DRY_RUN` tests exercise the full dispatch path without live TDLib.
5. **Additive migrations only.** Preserve old warmup sessions; no destructive rename/drop/not-null migration without a safe compatibility plan.
6. **Selector is the only decision point.** `channel_state.selector.choose_actions` decides action/target pairs. Dispatch resolves context, executes, and records results.
7. **Cross-cutting concerns stay outside warmup.** Survival analytics, lifecycle state machine, profile uniqueness, AI profile generation, and invite links are separate modules that warmup calls through public APIs.

## Forbidden

- Do not create a parallel warmup v2 module.
- Do not read mutable strategy fields from dispatch paths when a session snapshot can be used.
- Do not hardcode action selection in `dispatch_processor.py`.
- Do not add a real TDLib action without mock parity and `DRY_RUN` coverage.
- Do not enable live TDLib or live warmup without explicit operator approval.
- Do not store secrets, TDLib storage paths, raw logs, raw phone numbers, invite tokens, or generated asset blobs in `warmup_event.payload_json`.
- Do not put survival metrics, profile uniqueness, AI provider code, lifecycle state machine, or Grafana logic inside the warmup module.
- Do not let traffic-heavy metadata become an implicit runtime block. Runtime blocks belong to proxy adaptation or explicit operator escape hatches.

## Verify

Run the smallest relevant subset first:

```powershell
cd backend
python -m pytest tests/api/test_warmup_contracts.py -q
python -m pytest tests/test_warmup_dispatch_worker.py -q
python -m pytest tests/architecture/test_warmup_module_boundaries.py -q
```

For frontend warmup changes:

```powershell
npm run typecheck
npm test -- --run apps/dashboard/src/modules/warmup
```

For docs/memory-only warmup changes:

```powershell
npm run memory:check
npm run memory:sync:dry-run
```

## Update Memory

- Update `.mex/context/warmup-advanced-state.md` when implemented/planned state changes.
- Update `docs/design/warmup-advanced-file-map.md` for large file maps, action catalog changes, or milestone sequencing.
- Keep this pattern compact; it should remain a procedural checklist, not a design spec.
