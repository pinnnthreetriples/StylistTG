---
name: mex memory update
description: How to update the mex scaffold without creating drift.
triggers:
  - mex
  - memory
  - scaffold
edges:
  - .mex/ROUTER.md
  - .mex/context/decisions.md
  - .mex/patterns/INDEX.md
last_updated: 2026-05-10
---

# mex Memory Update

## Context

Load `.mex/ROUTER.md`, `.mex/context/decisions.md`, and the context file related to the changed knowledge.

## Steps

1. Update only stable, reusable project knowledge.
2. Keep `.mex` compact; link to detailed docs instead of copying full runbooks.
3. Keep `.mex/AGENTS.md` and root `AGENTS.md` synchronized.
4. Add patterns only for repeatable workflows.
5. Append decisions instead of deleting history.
6. Skip `.mex` edits for small code edits, typos, local debug notes, test-only changes, transient failures, and purely visual tweaks.

## Token Budget

- Prefer 1-5 concise bullets over long narrative sections.
- Do not copy large chunks from `AGENT_HANDOFF.md`, specs, or runbooks into `.mex`.
- Do not store transient task status, command output, stack traces, or one-off local findings.
- Add decisions only when the reason prevents future mistakes or explains a non-obvious tradeoff.
- Add patterns only after a workflow is repeatable, not after a one-off fix.

## Command Policy

- Run `npm run memory:check` after memory/docs/scaffold changes or when commands, paths, ports, routes, queues, feature flags, or architecture change.
- Do not run `npm run memory:check` after every small edit.
- Prefer `npm run memory:sync:dry-run`.
- Do not run `npm run memory:sync` without explicit user approval.

## Verify

```powershell
npm run memory:check
git diff --check
```

If `mex check` has false positives, document them before changing the scaffold around the tool.
