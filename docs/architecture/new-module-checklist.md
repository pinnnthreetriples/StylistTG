# New Module Checklist

Use this checklist before adding a backend or frontend feature module. It is intentionally compatibility-first: existing public paths, workflow identifiers, queue names, schemas, and worker behavior are contracts.

## Backend Files

- `backend/app/modules/<name>/__init__.py`
- `module.py` with `FeatureModule` metadata.
- `contracts.py` for Pydantic/API DTOs. No ORM, FastAPI, Redis, RQ, or TDLib imports.
- `router.py` for request parsing, auth/session dependencies, service calls, and error mapping.
- `service.py` facade for stable use-case entry points.
- `repository.py` for ORM query helpers.
- `policies.py` for pure business rules without DB/session/runtime imports.
- `errors.py` for module-scoped typed errors.
- `jobs.py` and `enqueue.py` only when the module owns workflows or queue entry points.

## Frontend Files

- `apps/dashboard/src/modules/<name>/index.ts`
- `api.ts`, `hooks.ts`, `types.ts`, `labels.ts` when useful.
- `components/` only for module-owned UI.
- Compatibility re-exports are allowed during migration, but new imports should prefer the public module index.

## Boundary Rules

- Routers do not import ORM models directly.
- Repositories may import ORM but not FastAPI/API helpers.
- Policies do not import DB/session/query APIs.
- Cross-module imports go through documented public surfaces.
- Legacy wrappers stay compatibility-only and must not regain new behavior.

## Workflow And Queue Rules

- Do not introduce replacement workflow types for existing persisted workflows.
- Add workflow metadata to `FeatureModule` and prove handler paths through tests.
- Add queue names only with explicit runtime role mapping, worker-plane descriptors, docs, and tests.
- Preserve deterministic job IDs and no-arg handlers when they already exist.

## OpenAPI And Security

- Run OpenAPI drift checks after contract movement.
- Keep workspace scoping and auth behavior unchanged unless the feature explicitly changes them.
- Do not expose secrets, raw TDLib paths, proxy credentials, auth codes, or unsafe message bodies.
- Update security/runtime docs when stable process, queue, or live-gate facts change.

## Rollout

- Add architecture tests before or with implementation.
- Add focused module/API/runtime tests.
- Update `.mex` memory when commands, paths, queues, modules, routes, or feature flags change.
- Document anything deferred with a concrete phase or removal condition.
