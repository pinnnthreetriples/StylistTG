# Broadcast Readiness

This is a readiness document only. It does not introduce broadcast runtime behavior, queues, workflows, routes, or frontend product surface.

## Purpose

Prepare the architecture questions for a future broadcast module that can safely plan and preview multi-account messaging work.

## Non-goals

- No backend broadcast module in this PR.
- No broadcast queue.
- No broadcast workflow type.
- No Telegram live send behavior.

## Required Contracts

- Workspace-scoped broadcast draft/read DTOs.
- Preview result DTO with target counts, blocking errors, warnings, and dedup metadata.
- Audit event DTOs for operator-visible actions.

## Safety Policies

- Preview/dry-run first.
- Workspace isolation for every target account and audience list.
- Rate limits per workspace, account, and recipient batch.
- Explicit operator approval before any future live send path.
- No message bodies in unsafe logs or generic diagnostics.

## Runtime

Future live execution would require a dedicated queue and runtime role. Until then, no queue name or workflow type is reserved in code.

## Frontend Entry Points

Future UI should live under `apps/dashboard/src/modules/broadcast/` with public exports through `index.ts`.
