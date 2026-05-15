# Storage Boundary

## Current State

`backend/app/models.py` remains the global ORM model module. This phase does not
split it or change migrations. Existing legacy services may still import ORM
models directly while their domains are migrated behind module repositories.

## Target State

Module-owned ORM access should live in repositories. Routers parse requests and
call use-case facades. Contracts define DTOs and do not import ORM/runtime
dependencies. Policies should express business rules without owning sessions,
queries, FastAPI, Redis, RQ, or TDLib adapters.

## Allowed Imports

- Repositories may import `app.models`, `sqlalchemy`, `sqlalchemy.orm.Session`,
  and query helpers needed for their module.
- Routers may import FastAPI and `sqlalchemy.orm.Session` for dependencies.
- Contracts may import `datetime`, `enum`, `typing`, and Pydantic.
- Policies may import module errors, module contracts, settings types, and pure
  helpers, but not DB/session/query or presentation infrastructure.

## Forbidden Imports

- Contracts must not import `app.models`, SQLAlchemy, FastAPI, Redis, RQ, or
  TDLib adapters.
- Module routers must not import `app.models` directly.
- Repositories must not import FastAPI, `app.api`, or `app.main`.
- Policies must not import `app.db`, SQLAlchemy sessions/query helpers,
  FastAPI/API helpers, Redis, RQ, or TDLib adapters.

## Transition Policy

When moving a feature under `app.modules.<feature>`, add a repository before
moving query helpers. Keep compatibility wrappers import-compatible, but put new
module behavior behind module repositories and service facades.

Temporary allowlist entries must be explicit in architecture tests with:

- exact source path;
- forbidden import being allowed;
- reason the import is temporarily necessary;
- removal condition or follow-up phase.

Do not broaden allowlists by directory unless every file in the directory has the
same documented reason.

