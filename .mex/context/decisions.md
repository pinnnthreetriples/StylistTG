---
name: decisions
description: Append-only decision log for memory-impacting project choices.
triggers:
  - decision
  - ADR
  - why
  - tradeoff
edges:
  - .mex/ROUTER.md
  - .mex/context/architecture.md
  - .mex/context/security.md
  - .mex/status/current.md
last_updated: 2026-06-08
---

# Decisions

## 2026-05-10 - Adopt mex as structured memory router

Status: superseded-by-2026-06-08-startup-anchor-restructure

Decision: use `.mex` as the structured project-memory entrypoint with `ROUTER.md`, compact context files, and task patterns.

Why: StylistTG is growing across backend, frontend, workers, warmup, cloud/staging, and security. A routed memory scaffold reduces token load and makes drift easier to detect.

Consequence: `.mex` summarizes and routes; detailed docs stay in `docs/`.

## 2026-05-10 - Preserve legacy AGENT_HANDOFF during migration

Status: superseded-by-2026-06-08-handoff-archive

Decision: keep `AGENT_HANDOFF.md` as a legacy/full snapshot while `.mex` becomes the structured entrypoint.

Why: deleting or fully replacing the handoff in one step risks losing context. Migration should be reversible until mex CLI checks are stable.

Consequence: new agents read `.mex/ROUTER.md` first, then consult archived historical handoff only when current `.mex` memory and `docs/` do not answer the question.

## 2026-05-10 - Keep local dashboard backend port at 8002

Status: active

Decision: local dashboard dev uses backend port `8002`; live-validation helper scripts may continue to default to `8000`.

Why: `scripts/start-dev.ps1` and Vite proxy expect `8002`, while `scripts/start_backend.ps1` is used by live-validation style flows.

Consequence: docs and memory must distinguish local dashboard dev from live validation instead of replacing every `8000`.

## 2026-05-10 - Warmup live behavior remains explicitly gated

Status: active

Decision: warmup dry-run/shadow flows are documented, but live warmup requires explicit operator approval and feature gates.

Why: live Telegram behavior can affect real accounts and must not be enabled by automation or documentation drift.

Consequence: `WARMUP_LIVE_ENABLED` plus mode-specific flags are required, and agents must not enable them without approval.

## 2026-05-10 - Keep mex updates conservative

Status: active

Decision: run `npm run memory:check` after memory/docs/scaffold changes or stable changes to commands, paths, ports, routes, queues, feature flags, or architecture; do not run it after every small edit. Prefer `npm run memory:sync:dry-run`, and do not run `npm run memory:sync` without explicit user approval.

Why: memory checks and sync flows should prevent drift without wasting tokens or encouraging noisy memory updates.

Consequence: `.mex` grows only for stable, reusable project knowledge; skip memory edits for small code edits, typos, local debug notes, test-only changes, transient failures, and purely visual tweaks.

## 2026-06-08 - Make AGENTS.md canonical and keep tool anchors thin

Status: active

Decision: `AGENTS.md` is the canonical cross-agent startup anchor. `CLAUDE.md` imports it and contains Claude Code-specific notes only. `.mex/AGENTS.md` is a mex compatibility pointer only.

Why: Codex, Claude Code, and mex need different entry files, but long duplicated instructions drift.

Consequence: update shared startup rules only in `AGENTS.md`; keep tool-specific files thin and route non-trivial work through `.mex/ROUTER.md`.

## 2026-06-08 - Add status/current for temporary project state

Status: active

Decision: temporary runtime, rollout, safety, deploy, or migration state belongs in `.mex/status/current.md` with `review_after` metadata.

Why: temporary state becomes stale when placed in startup anchors or stable context files.

Consequence: agents must read `.mex/status/current.md` before safety, live TDLib, warmup, rollout, or deploy work, and must not treat temporary status as permanent architecture.

## 2026-06-08 - Archive legacy handoff instead of using it as startup memory

Status: active

Decision: root `AGENT_HANDOFF.md` is a compatibility pointer. The long-form historical snapshot should live under `docs/archive/agent-handoff-2026-05.md`.

Why: startup memory must stay compact, but historical context should remain available without requiring agents to inspect Git history.

Consequence: `.mex` is the structured current source of truth; archived handoff is historical fallback only.

## 2026-06-08 - Split Advanced Warmup procedure from design map

Status: active

Decision: `.mex/patterns/warmup-advanced.md` stores compact procedural rules. Large planned file maps, action catalogs, and lifecycle notes live in `docs/design/warmup-advanced-file-map.md`. Current milestone state lives in `.mex/context/warmup-advanced-state.md`.

Why: mex patterns should be repeatable workflows, not long design specs.

Consequence: agents load the compact pattern for implementation work and only open the large design map when they need planned file/action details.
