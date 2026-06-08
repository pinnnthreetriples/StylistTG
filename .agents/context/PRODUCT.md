---
register: product
last_updated: 2026-06-08
---

# StylistTG Product Context

## Product Purpose

StylistTG is a local operator dashboard for account onboarding, profile editing, media workflows, diagnostics, preparation sessions, job progress, and runtime readiness.

## Users

- Technical operator managing account workflows.
- Developer/operator debugging backend readiness, workers, queues, Redis, storage, and safety gates.

## Product Rules

- UI should be minimal, clean, compact, and not visually bulky.
- User-facing dashboard labels and tooltips should be Russian unless a technical identifier is clearer in English.
- Prioritize readiness, state, next action, and verification over decorative dashboards.
- Safety and live-operation states must be explicit: disabled, gated, dry-run, shadow, live, blocked, warning.

## Anti-References

- No exaggerated product claims.
- No heavy nested cards or duplicated status panels.
- No UI copy that hides live-operation risk.
