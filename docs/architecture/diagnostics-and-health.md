# Diagnostics and Health

Health Center consumes backend-backed diagnostics instead of inferring runtime posture from frontend environment variables.

## Endpoints

- `GET /health`: liveness only.
- `GET /ready`: readiness for database, Redis, and TDLib configuration status.
- `GET /diagnostics/frontend-summary`: safe dashboard summary for app/runtime posture.
- `GET /api/accounts/risk-summary`: tenant-scoped account readiness risk summary.

## Frontend Summary Contract

`/diagnostics/frontend-summary` returns metadata only:

- app environment;
- auth mode;
- DB status and connection mode;
- Redis status and configured flag;
- storage backend and safe posture flags;
- TDLib status, profile execution adapter, and live-enabled flag;
- expected worker queues;
- backend-generated timestamp.

It must never return raw DB URLs, Redis URLs, S3 keys, Supabase secrets, JWTs, TDLib filesystem paths, session metadata, or tracebacks.

## Dashboard Behavior

Health Center shows:

- API liveness;
- DB and Redis readiness;
- TDLib mock/not-configured/live-disabled posture;
- storage/auth/app runtime summary from the backend;
- backend account risk summary;
- loading and error states with retry.

These endpoints are safe read-only diagnostics. They do not run cleanup/reaper, live Telegram/TDLib actions, profile/story/music jobs, or account import execution.
