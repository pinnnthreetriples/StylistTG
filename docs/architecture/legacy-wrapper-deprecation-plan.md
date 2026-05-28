# Legacy Wrapper Deprecation Plan

Generated snapshot: `2026-05-17T00:00:00Z`

## Purpose

Legacy wrappers keep old API, service, and worker import paths stable while canonical ownership moves to `app.modules`. This plan defines how those wrappers can be deprecated and eventually removed without changing runtime behavior in this PR.

## Current Wrapper Inventory

The machine-readable source is `docs/architecture/legacy-wrappers.json`, validated by `backend/scripts/legacy_wrapper_audit.py`.

| Legacy area | Current stage | Canonical owners |
| --- | --- | --- |
| Account lifecycle API/service wrappers | Stage 0 compatibility active | `app.modules.account_lifecycle.router`, `service`, `retention` |
| Account update API/service/worker wrappers | Stage 0 compatibility active | `app.modules.account_editing.router`, `service`, `planner`, `executor` |
| Account safety API/service/contract wrappers | Stage 0 compatibility active | `app.modules.account_safety.router`, `accounts_router`, `policy_router`, `read_models`, `batch_preview`, `gate`, `cache`, `reserve`, `overrides`, `policy`, `action_gate`, `read_contracts`, `gate_contracts` |
| Auth context wrapper | Stage 0 compatibility active | `app.modules.auth.dependencies / context` |
| Neuro-commenting API/service wrappers | Stage 0 compatibility active | `app.modules.neuro_commenting.router` and service implementation modules |
| Warmup API/service/worker wrappers | Stage 0 compatibility active | `app.modules.warmup.router`, `service`, `dispatcher`, `isolation`, `readiness`, `p2p`, `worker`, `jobs` |

## Canonical Owners

- Account editing behavior belongs under `app.modules.account_editing`.
- Account lifecycle behavior belongs under `app.modules.account_lifecycle`.
- Account safety behavior belongs under `app.modules.account_safety`.
- Auth dependency/context behavior belongs under `app.modules.auth`.
- Neuro-commenting behavior belongs under `app.modules.neuro_commenting`.
- Warmup behavior belongs under `app.modules.warmup`.
- Legacy wrappers may re-export or delegate only to canonical owners.

## Allowed Use Cases

- External compatibility for users or scripts importing old paths.
- Existing tests that intentionally verify compatibility.
- API router registration paths that have not yet been migrated.
- Workflow registry compatibility paths until a dedicated worker import migration is complete.

## Forbidden New Use Cases

- New module code importing `app.services.*` or `app.workers.*` legacy wrappers.
- New behavior, validation, branching, side effects, warnings, or logging inside wrappers.
- Runtime `DeprecationWarning` at import time.
- Wrapper export changes outside a dedicated compatibility migration.

## Deprecation Stages

| Stage | Meaning | Exit criteria |
| --- | --- | --- |
| Stage 0 - Compatibility active | Wrapper exists and old imports work. | Manifest and tests identify canonical owner and forbid module imports. |
| Stage 1 - No new imports allowed | Static checks block new internal imports. | Existing internal call-sites are inventoried. |
| Stage 2 - Internal call-sites migrated | Backend app internals use canonical module paths. | Tests pass with app internals migrated. |
| Stage 3 - Tests migrated | Tests stop relying on wrappers except compatibility-specific tests. | Compatibility tests are narrow and intentional. |
| Stage 4 - External/user import risk assessed | External import risk is reviewed. | Release notes or operator notice are prepared if needed. |
| Stage 5 - Wrapper removal PR | Dedicated PR removes wrappers. | All blockers cleared and rollback is documented. |

## Removal Criteria

- No `backend/app/modules` imports of legacy wrappers.
- No non-compatibility backend internal imports of legacy wrappers.
- Compatibility tests are the only remaining wrapper import tests.
- Workflow registry and worker entrypoints no longer require old paths.
- External/user import risk is assessed and accepted.
- Dedicated removal PR includes rollback instructions.

## Risk Matrix

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Breaking old imports | High | Keep wrappers until Stage 5 and require manifest/tests. |
| Runtime warning noise | Medium | Forbid import-time warnings in wrappers. |
| Behavior drift between wrapper and owner | Medium | Wrappers must only delegate/re-export canonical owners. |
| Hidden internal imports linger | Medium | Static audit blocks module imports and tracks manifest entries. |
| Removing worker paths too early | High | Workflow registry compatibility remains a blocker until explicitly migrated. |

## Testing Strategy

- `backend/scripts/legacy_wrapper_audit.py` validates deterministic `legacy-wrappers.json` and wrapper files; `--print` emits regenerated content for review.
- Architecture tests verify manifest validity, wrapper markers, canonical owners, valid stages, no module imports of wrappers, and script/manifest consistency.
- Existing behavior tests continue to cover old imports until a dedicated removal PR.

## Rollback Strategy

- For Stage 0-4 changes, rollback by restoring the previous manifest/docs/tests; wrapper runtime code is unchanged.
- For a future Stage 5 removal PR, rollback by restoring removed wrapper files with their last compatibility docstrings and re-running architecture tests.

## Current Status

All wrappers remain in `stage_0_compatibility_active`. No wrapper is removed, renamed, or deprecated at runtime in this PR.
Architecture Epic Phase 6C still treats behavior-free canonical wrappers as
accepted compatibility evidence. That acceptance does not apply to active
residual legacy feature boundaries, which remain visible architecture debt until
migrated or reduced to wrappers. Wrapper retirement remains a separate
behavior-preserving compatibility program.
