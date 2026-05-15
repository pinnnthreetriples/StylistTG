# Runtime Boundaries

StylistTG runs one backend image in several runtime roles. The image can stay shared, but process commands, queue access, TDLib/session assumptions, and blast radius must be role-specific.

No role metadata in this document enables live TDLib by itself. Existing feature gates and operator approval remain required.

## Roles

| Role | Purpose | Queues | TDLib/session access | Storage/Redis/DB | Live TDLib | Startup |
| --- | --- | --- | --- | --- | --- | --- |
| `api` | FastAPI request handling and module routers. | None. | No direct TDLib/session access. | DB and Redis only through existing app services/infrastructure. | No. | API server command. |
| `scheduler` | Scheduled enqueue decisions and safe ticks. | `scheduler_jobs` | No TDLib/session access. | Redis enqueue and DB reads/writes needed for scheduling. | No. | scheduler process or worker role. |
| `reaper` | Stale job reconciliation outside API replicas. | None. | No TDLib/session access. | DB and Redis inspection/reconciliation. | No. | reaper process. |
| `auth_worker` | Telegram auth and reauth execution. | `auth_jobs` | Requires TDLib runtime and per-account session storage. | Redis worker queue and DB job/account writes. | Explicitly allowed, still gated. | `python -m app.workers.run_worker --queues auth_jobs --role auth_worker` |
| `profile_worker` | Profile/account update execution. | `profile_jobs` | Requires TDLib runtime and per-account session storage. | Redis worker queue and DB job/account writes. | Explicitly allowed, still gated. | `python -m app.workers.run_worker --queues profile_jobs --role profile_worker` |
| `warmup_worker` | Dry-run account preparation jobs. | `warmup_jobs` | No live TDLib/session requirement. | Redis worker queue and warmup DB writes. | No. | `python -m app.workers.run_worker --queues warmup_jobs --role warmup_worker` |
| `warmup_dispatch_worker` | Warmup micro-session dispatch. | `warmup_dispatch_jobs` | Requires TDLib runtime and per-account session storage. | Redis worker queue and warmup DB writes. | Explicitly allowed, still gated. | `python -m app.workers.run_worker --queues warmup_dispatch_jobs --role warmup_dispatch_worker` |
| `maintenance_worker` | Maintenance and reserved queue taxonomy. | `maintenance_jobs`, `media_jobs`, `story_jobs`, `account_lifecycle_jobs` | No TDLib/session requirement in this phase. | Redis worker queue and DB access as needed by future maintenance jobs. | No. | role-specific worker command when these queues are active. |

## Enforcement

`backend/app/runtime/roles.py` is the executable registry for runtime roles. `app.workers.run_worker` keeps the legacy `--queues` mode and adds optional `--role` validation. When `--role` is supplied, every requested queue must belong to the role.

Reserved queues remain assigned to `maintenance_worker` until dedicated roles exist. New queues require an update to `app.services.worker_plane`, this document, runtime role tests, and deployment runbooks.

## Preflight

`backend/app/runtime/preflight.py` provides internal, non-live checks for role metadata, queue allowlists, TDLib-required flags, live-allowed flags, and session-root configuration. It must not read Telegram session directories or call TDLib.

## Health Expectations

- API health should not imply worker or TDLib readiness.
- Worker preflight should be role-specific before queue consumption.
- TDLib runtime availability and live gates must remain explicit and safe by default.
- Session paths must not be exposed in user-facing diagnostics.
