# Backend Boundary Enforcement

## Goal

Phase 5 turns modular backend boundaries into executable checks. The goal is to
prevent architecture drift without changing runtime behavior.

The current backend modules are:

```text
backend/app/modules/account_editing
backend/app/modules/warmup
```

Future modules should follow the same rules before adding runtime dependencies.

## Public Module Surfaces

Every package under `app.modules` must define an explicit `__all__` in
`__init__.py`.

Rules:

- no wildcard exports;
- no implicit "export everything" package behavior;
- runtime-heavy facades may stay in explicit submodules to avoid registry import
  cycles;
- consumers should import stable package submodules or documented public
  contracts.

Good:

```python
from app.modules.warmup import service
from app.modules.account_editing import errors
from app.modules.account_editing.service import create_job
```

Bad:

```python
from app.modules.warmup.dispatcher_private import RawDispatcherState
from app.modules.account_editing.repository import AccountEditingRepository  # from another module
```

Direct imports of a module's own internals are allowed inside that same module.
Imports across feature modules must use the target module package, `contracts`,
`interfaces`, `service`, `jobs`, or `events`.

## Allowed Dependency Direction

Allowed direction:

```text
app.api -> app.modules / app.services
app.workers -> app.modules / app.services
app.modules -> shared app.services / app.adapters / app.storage
app.modules.<feature> -> app.modules.<same feature>
```

Forbidden direction:

```text
app.modules / app.services / app.workers -> app.api
repositories -> FastAPI or app.api
feature module internals -> another feature module internals
```

The architecture tests report the source file, offending import, and expected
boundary when a rule is violated.

## FastAPI Boundary

FastAPI belongs in the presentation layer:

- `app.api`
- `app.main`
- `app.errors`

FastAPI imports are blocked in modules, workers, job queues, storage, adapters,
and services, except for the existing `app.services.auth_context` bridge. That
allowlist is explicit in the architecture test and should not grow without a
clear migration reason.

## API Contracts And ORM Models

Schema/contract modules must not import raw SQLAlchemy models from `app.models`.
API contracts should use Pydantic models, enums, primitive IDs, and explicit DTOs.

This does not ban routers or services from querying ORM models. It only prevents
API contract modules from exposing ORM classes as the contract itself.

## Adding A New Module

1. Create `backend/app/modules/<name>/__init__.py` with explicit `__all__`.
2. Add module metadata in `<name>/module.py` if the module owns workflows.
3. Keep public contracts in `contracts.py` or `interfaces.py` when other modules
   need to depend on them.
4. Do not import another module's repository, policies, planner, executor, or
   other internal files.
5. Add or extend architecture tests if the module needs a new public boundary.

## Extending Contracts Safely

Prefer narrow contracts:

```python
from app.modules.some_module.contracts import SomeSnapshot
```

Avoid exposing implementation owners:

```python
from app.modules.some_module.repository import SomeRepository
```

If a future module needs a shared capability, move the shared abstraction to an
explicit contract/interface or a shared service before importing it.

## Current Enforcement Tests

The enforced checks live in `backend/tests/architecture/`:

- `test_no_cross_module_internal_imports.py`
- `test_dependency_direction.py`
- `test_no_fastapi_in_domain.py`
- `test_no_sqlalchemy_models_in_api_contracts.py`

They run in normal `pytest` and require no additional runtime dependency.
