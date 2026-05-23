---
name: StylistTG agent anchor
description: Shared agent entrypoint. Keep in sync with .mex/AGENTS.md and CLAUDE.md.
last_updated: 2026-05-23
---

# StylistTG

Telegram account/profile automation platform: React/TS/Vite monorepo + FastAPI + RQ/Redis + TDLib.

## Non-Negotiables

- Read `.mex/ROUTER.md` before non-trivial work.
- Never read, commit, or copy secrets/runtime data; `.env*`, `backend/tdlib/`, logs, and artifacts are local-only unless explicitly approved.
- Do not run live TDLib/Telegram calls or live warmup behavior without explicit operator approval.
- Ask before `npm install`, `pip install`, file deletion, git push, or production-like operations.
- Make minimal, surgical changes and verify with targeted checks.
- Use package @stylisttg/ui for dashboard product UI when an equivalent exists.
- When Serena MCP is available, activate `C:\Users\user\Documents\workspace-codex\StylistTG` before using Serena memories or symbol tools.
- Before GitHub issue, pull request, or project-board work, read `docs/agents/project-board.md`; the StylistTG Development board is the source of truth for active work.

## Agent skills

Use only StylistTG project skills from the active agent runtime's project skill directory in this section. Global skills are configured outside this repository and do not need to be repeated here.

### Setup and Context

- `/setup-matt-pocock-skills`: Use when project skill configuration is missing or stale. Issue tracker, triage labels, and domain-doc layout are documented in `docs/agents/`.
- `/grill-with-docs`: Use to stress-test a plan against StylistTG domain language, `.mex` context, and documented decisions before implementation.
- `/zoom-out`: Use when the agent or user needs a higher-level map of an unfamiliar StylistTG area, including relevant modules, callers, and domain terms.

### Engineering Workflow

- `/tdd`: Use for feature work and bug fixes where behavior can be specified with tests first. Prefer behavior/integration tests through public interfaces.
- `/diagnose`: Use for bugs, failures, regressions, or unclear broken behavior. Reproduce, minimize, hypothesize, instrument, fix, then add regression coverage.
- `/prototype`: Use for throwaway experiments that answer a design, state, data-model, or UI question before committing to production code.
- `/improve-codebase-architecture`: Use for architecture reviews, refactoring opportunities, testability improvements, or AI-navigability improvements.

### Product and Issue Workflow

- `/to-prd`: Use to turn current context into a PRD for the project issue tracker without re-interviewing the user.
- `/to-issues`: Use to break a plan, spec, or PRD into independently grabbable GitHub issues using vertical slices.

### Project Skill Configuration

- Issue tracker: GitHub Issues for the origin repository; see `docs/agents/issue-tracker.md`.
- Project board workflow: `docs/agents/project-board.md`.
- Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`; see `docs/agents/triage-labels.md`.
- Domain docs: `.mex/ROUTER.md` is the entrypoint; `.mex/context/` and `.mex/patterns/` are the domain source of truth; see `docs/agents/domain.md`.

## Core Commands

```powershell
.\scripts\start-dev.ps1
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
cd backend; python -m pytest -q
cd backend; python -m ruff check .
```

## Memory Commands

- Run `npm run memory:check` after memory/docs/scaffold changes or when commands, paths, ports, routes, queues, feature flags, or architecture change.
- Do not run `npm run memory:check` after every small code edit, test-only change, typo, local debug step, or purely visual tweak.
- Prefer `npm run memory:sync:dry-run`; do not run `npm run memory:sync` without explicit user approval.

## Memory

- `.mex/AGENTS.md` is the canonical mex source anchor; root `AGENTS.md` is the Codex-facing copy and root `CLAUDE.md` is the Claude-facing copy.
- Keep `.mex/AGENTS.md`, root `AGENTS.md`, and root `CLAUDE.md` synchronized when stable agent instructions change.
- `.mex/ROUTER.md` is the structured memory router and should be read first.
- `AGENT_HANDOFF.md` is retained as a legacy/full handoff snapshot during migration.
- Detailed docs remain in `docs/` and specs remain in `specs/`.
