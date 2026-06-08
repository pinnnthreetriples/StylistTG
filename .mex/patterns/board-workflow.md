---
name: board-workflow
description: Minimal mex pattern for GitHub Project board status transitions.
edges:
  - .mex/ROUTER.md
  - docs/agents/project-board.md
last_updated: 2026-06-08
---

# Board Workflow Pattern

Canonical project-board instructions live in `docs/agents/project-board.md`.
Use this mex pattern as the compact session checklist.

## Minimal Checklist

1. Identify the target issue.
2. Fetch board metadata only when a board update is required.
3. Move the item to `In Progress` when work starts.
4. Comment on the issue with branch, intent, and scope.
5. Keep issue comments current if scope changes or blockers appear.
6. Open a PR with verification notes and `Closes #N` when implementation is ready.
7. Move the item to `Review` after the PR is opened.
8. Move the item to `Done` only after the PR is merged and the issue is closed.

## Rules

- Fetch project field and option IDs dynamically; never hardcode them across sessions.
- Verify board mutations before reporting success.
- If the token lacks `project` scope, report the blocker and continue code/docs work without pretending the board was updated.
- Keep GraphQL/API examples in `docs/agents/project-board.md`; do not duplicate them here.
