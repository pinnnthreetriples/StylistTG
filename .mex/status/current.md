---
name: current project status
description: Temporary project state agents must check before safety, live TDLib, warmup, rollout, or deploy work.
last_updated: 2026-06-08
review_after: 2026-06-22
status: active
---

# Current Project Status

## Workspace Safety Policy

Status: temporarily disabled by developer decision on 2026-06-04.

`WORKSPACE_SAFETY_POLICY_TEMPORARILY_DISABLED` defaults to `True`. While enabled, `get_workspace_safety_policy()` returns a neutral transient policy for consumers including safety gate, quarantine, status monitor, neuro-commenting, and warmup.

Do not describe the safety pipeline as fully active until this status is superseded. The foundation exists, but workspace-wide behavioral limits, quiet hours, and auto-pauses are neutralized while the kill-switch is on.

Re-enable only after per-account behavior ships and absorbs the duplicated behavioral fields:

- personality seed;
- channel-state selector;
- circadian windows.

Re-enable path and rollback details live in `docs/runbooks/safety-rollout.md`.

## Documentation Drift Reminders

- Safety rollout/preflight docs must reference current Alembic `head`, including `20260526_0056` and merge revision `20260526_0057`.
- `AGENT_HANDOFF.md` is historical only; current structured memory lives in `.mex/`.
- Port examples should use `$ApiBaseUrl` or the startup output. Do not assume `8000` when dashboard local development uses `8002`.
