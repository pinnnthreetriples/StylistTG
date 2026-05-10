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
last_updated: 2026-05-10
---

# Decisions

## 2026-05-10 - Adopt mex as structured memory router

Decision: use `.mex` as the structured project-memory entrypoint with `ROUTER.md`, compact context files, and task patterns.

Why: StylistTG is growing across backend, frontend, workers, warmup, cloud/staging, and security. A routed memory scaffold reduces token load and makes drift easier to detect.

Consequence: `.mex` summarizes and routes; detailed docs stay in `docs/`. Root `AGENTS.md` stays synchronized with `.mex/AGENTS.md`.

## 2026-05-10 - Preserve legacy AGENT_HANDOFF during migration

Decision: keep `AGENT_HANDOFF.md` as a legacy/full snapshot while `.mex` becomes the structured entrypoint.

Why: deleting or fully replacing the handoff in one step risks losing context. Migration should be reversible until mex CLI checks are stable.

Consequence: new agents read `.mex/ROUTER.md` first, then consult `AGENT_HANDOFF.md` only for deeper historical context.

## 2026-05-10 - Keep local dashboard backend port at 8002

Decision: local dashboard dev uses backend port `8002`; live-validation helper scripts may continue to default to `8000`.

Why: `scripts/start-dev.ps1` and Vite proxy expect `8002`, while `scripts/start_backend.ps1` is used by live-validation style flows.

Consequence: docs and memory must distinguish local dashboard dev from live validation instead of replacing every `8000`.

## 2026-05-10 - Warmup live behavior remains explicitly gated

Decision: warmup dry-run/shadow flows are documented, but live warmup requires explicit operator approval and feature gates.

Why: live Telegram behavior can affect real accounts and must not be enabled by automation or documentation drift.

Consequence: `WARMUP_LIVE_ENABLED` plus mode-specific flags are required, and agents must not enable them without approval.

## 2026-05-10 - Keep mex updates conservative

Decision: run `npm run memory:check` after memory/docs/scaffold changes or stable changes to commands, paths, ports, routes, queues, feature flags, or architecture; do not run it after every small edit. Prefer `npm run memory:sync:dry-run`, and do not run `npm run memory:sync` without explicit user approval.

Why: memory checks and sync flows should prevent drift without wasting tokens or encouraging noisy memory updates.

Consequence: `.mex` grows only for stable, reusable project knowledge; skip memory edits for small code edits, typos, local debug notes, test-only changes, transient failures, and purely visual tweaks.
