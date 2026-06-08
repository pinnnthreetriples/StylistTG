---
name: StylistTG agent anchor
description: Canonical cross-agent startup entrypoint for Codex and other AGENTS.md-aware agents.
last_updated: 2026-06-08
---

# StylistTG

Telegram account/profile automation platform: React/TS/Vite monorepo + FastAPI + RQ/Redis + TDLib.

## Non-Negotiables

- Read `.mex/ROUTER.md` before non-trivial work.
- Check `.mex/status/current.md` before safety, live TDLib, warmup, deploy, or rollout work.
- Never read, commit, copy, or summarize secrets/runtime data; `.env*`, `backend/tdlib/`, logs, and artifacts are local-only unless explicitly approved.
- Do not run live TDLib/Telegram calls or live warmup behavior without explicit operator approval.
- Ask before `npm install`, `pip install`, file deletion, git push, branch protection changes, or production-like operations.
- Make minimal, surgical changes and verify with targeted checks.
- Use package `@stylisttg/ui` for dashboard product UI when an equivalent exists.
- When Serena MCP is available, activate `C:\Users\user\Documents\workspace-codex\StylistTG` before using Serena memories or symbol tools.
- Before GitHub issue, pull request, or project-board work, read `docs/agents/project-board.md`; the StylistTG Development board is the source of truth for active work.
- When working on a board issue, follow `.mex/patterns/board-workflow.md` for status transitions.

## Agent Skills

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
- `/git-guardrails-claude-code`: Use to set up hooks that block dangerous git commands before execution.

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
npm run design:detect
npm run impeccable:check
npm run impeccable:skills
cd backend; python -m pytest -q
cd backend; python -m ruff check .
```

## Memory Commands

- Run `npm run memory:check` after memory/docs/scaffold changes or when commands, paths, ports, routes, queues, feature flags, or architecture change.
- Do not run `npm run memory:check` after every small code edit, test-only change, typo, local debug step, or purely visual tweak.
- Prefer `npm run memory:sync:dry-run`; do not run `npm run memory:sync` without explicit user approval.

## Memory Structure

- `AGENTS.md` is the canonical cross-agent startup anchor.
- `CLAUDE.md` imports `AGENTS.md` and contains Claude Code-specific notes only.
- `.mex/AGENTS.md` is a mex compatibility pointer only.
- `.mex/ROUTER.md` is the structured mex memory router and should be read first for non-trivial work.
- `.mex/status/current.md` stores temporary project state with review dates.
- `.mex/context/` stores stable semantic project memory.
- `.mex/patterns/` stores repeatable procedural workflows.
- `docs/archive/` stores historical snapshots such as old handoffs.
- Detailed docs remain in `docs/` and specs remain in `specs/`.

## Memory Update Policy

- Update memory only for stable, reusable project knowledge.
- Do not store logs, stack traces, raw command output, secrets, local-only artifacts, or one-off task notes in memory.
- Put temporary rollout state in `.mex/status/current.md` with `review_after`.
- Put architectural decisions in `.mex/context/decisions.md`.
- Put repeated workflows in `.mex/patterns/` only after they are useful across tasks.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
