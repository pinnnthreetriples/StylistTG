<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles: template placeholders -> StylistTG project principles
Added sections: Additional Constraints, Development Workflow
Removed sections: placeholder examples
Templates requiring updates: none in this documentation-only pass
Deferred items: none
-->

# StylistTG Constitution

## Core Principles

### I. Workspace and Secret Safety

Secrets, `.env*`, TDLib sessions, logs, artifacts, auth codes, proxy passwords, raw runtime paths, and private operator data MUST NOT be read, copied, summarized, committed, or stored in memory unless the operator explicitly approves the exact file and action. Documentation and memory must summarize safe structure only.

### II. PostgreSQL Source of Truth

PostgreSQL-backed models are the source of truth for accounts, profile state, warmup state, jobs, audits, workspaces, and policy state. Redis/RQ is execution infrastructure and cache state only. Agents must not describe Redis, local files, or frontend state as canonical persisted state.

### III. Live Runtime Explicitly Gated

Live TDLib, live account mutation, live warmup, cloud deploy, migrations, and production-like smoke MUST remain disabled or unexecuted unless the operator explicitly approves the action and the feature-specific gates are satisfied. Dry-run, shadow, and preview paths must remain clearly labeled.

### IV. Thin API and Module Ownership

FastAPI route handlers validate, authorize, and delegate. Business behavior belongs in module-owned services, facades, repositories, contracts, and workflow helpers under `backend/app/modules/` or documented compatibility surfaces. Legacy wrappers must not become new ownership centers.

### V. Verifiable Vertical Slices

Every behavior change must include the smallest useful verification: targeted tests, typecheck, lint, smoke, generated API drift check, or documented manual check. Agents must report checks run, checks skipped, and the reason for any skipped check.

### VI. Routed Compact Memory

`AGENTS.md` and `.mex/ROUTER.md` are the startup path. `.mex/status/` stores temporary project state, `.mex/context/` stores stable semantic memory, `.mex/patterns/` stores repeatable procedures, and `docs/archive/` stores historical snapshots. Startup anchors must remain compact and must not duplicate long runbooks.

## Additional Constraints

- UI work must use `@stylisttg/ui` primitives when an equivalent exists.
- Frontend remains polling-first unless a documented architecture decision changes it.
- Dashboard user-facing copy should be Russian unless a technical identifier is clearer in English.
- Warmup, safety, and readiness features must not be described as guarantees of external platform outcomes.
- Generated OpenAPI artifacts must be updated through `npm run generate:api` and checked with `npm run check:api` after backend route/schema changes.

## Development Workflow

- Start from `AGENTS.md`, then read `.mex/ROUTER.md` and `.mex/status/current.md` for non-trivial work.
- Load only the routed context and pattern for the task.
- Prefer targeted tests and verification over broad expensive checks unless the change needs broad coverage.
- Update memory only for stable reusable knowledge, not logs, one-off command output, local debug notes, or transient task status.
- Board/issue/PR work must follow `docs/agents/project-board.md` and `.mex/patterns/board-workflow.md`.

## Governance

This constitution supersedes lower-level agent guidance when conflicts exist. Amendments require a decision entry in `.mex/context/decisions.md`, an updated version/date below, and review of affected `.mex` memory, Spec Kit templates, and runbooks. Versioning follows semantic versioning: MAJOR for incompatible governance changes, MINOR for new principles or sections, PATCH for clarifications.

**Version**: 1.0.0 | **Ratified**: 2026-06-08 | **Last Amended**: 2026-06-08
