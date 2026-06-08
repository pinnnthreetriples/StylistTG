---
status: planned
implemented: false
runtime: none
queue: none
frontend_surface: none
last_updated: 2026-06-08
---

# Analytics Readiness

This is a readiness document only. It does not introduce analytics runtime behavior, queues, workflows, routes, or frontend product surface.

## Purpose

Prepare a future analytics module around workspace-scoped reporting without coupling feature modules to ad hoc dashboards.

## Non-goals

- No backend analytics module in this PR.
- No analytics queue.
- No analytics workflow type.
- No new metrics ingestion runtime.

## Required Contracts

- Workspace-scoped report query DTOs.
- Aggregated read models that avoid exposing raw secret, TDLib, proxy, or message data.
- Export contracts only after storage and authorization policy is explicit.

## Safety Policies

- No cross-workspace aggregation.
- No raw PII exports by default.
- Redaction rules for account identifiers and operational metadata.
- Rate limits for expensive report generation.

## Runtime

Analytics should start as read/query behavior. Any future async report generation needs an explicit queue, workflow metadata, runtime role ownership, and architecture tests.

## Frontend Entry Points

Future UI should live under `apps/dashboard/src/modules/analytics/` with public exports through `index.ts`.
