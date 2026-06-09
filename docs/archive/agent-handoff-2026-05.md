---
status: archived
source: AGENT_HANDOFF.md
source_commit: ab00e77f5b6408996d1d42840e1ec3f34ea840e2
archived_on: 2026-06-08
---

# Archived Agent Handoff — 2026-05

This archive preserves the location and purpose of the legacy long-form agent handoff that existed before the mex memory restructure.

The current project memory source of truth is `.mex/`:

1. `AGENTS.md`
2. `.mex/ROUTER.md`
3. `.mex/status/current.md`
4. routed files under `.mex/context/` and `.mex/patterns/`

## Historical source

The original long-form handoff content is available in repository history at commit `ab00e77f5b6408996d1d42840e1ec3f34ea840e2` in root `AGENT_HANDOFF.md`.

Use this archive only as historical fallback when current `.mex` memory and `docs/` do not answer a question.

## Historical scope captured by the old handoff

The old handoff covered:

- local Telegram account/profile automation scope;
- React/Vite dashboard and FastAPI backend layout;
- TDLib auth/profile/story/music execution notes;
- RQ/Redis worker expectations;
- SaaS backend foundation and staging/deploy notes;
- frontend routing and dashboard UX notes;
- account preparation/warmup foundation;
- live-validation caveats;
- old startup expectations for agents before the mex restructure.

## Important caveat

Treat the historical handoff as stale unless a fact is confirmed in current `.mex/context/`, current `docs/`, or source code. Do not use it as startup memory and do not expand task scope based on archived content.
