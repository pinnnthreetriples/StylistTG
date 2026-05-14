# Warmup Module

## Goal

`app.modules.warmup` is the canonical module boundary for Account Preparation /
Warmup workflow metadata, API contracts, use cases, and job entrypoints.

This is an ownership migration, not a warmup redesign. Public API behavior,
execution modes, workflow types, queues, deterministic job ids, no-arg handlers,
TDLib/live gates, and legacy import paths remain stable.

## Canonical Module Path

The canonical warmup module boundary is:

```text
backend/app/modules/warmup/
  __init__.py
  module.py
  contracts.py
  repository.py
  policies.py
  errors.py
  read_models.py
  queries.py
  commands.py
  service.py
  router.py
  jobs.py
  worker.py
  dispatcher.py
  events.py
  isolation.py
  readiness.py
  p2p.py
```

Ownership:

- `contracts.py` owns warmup Pydantic API DTOs and must not import ORM/runtime
  dependencies.
- `repository.py` owns ORM query helpers and must not import FastAPI or API
  helpers.
- `policies.py` owns warmup business rules and status-transition decisions.
- `errors.py` owns module-scoped typed warmup errors.
- `read_models.py` owns DTO assembly from warmup runtime state.
- `queries.py` owns read-only warmup use cases.
- `commands.py` owns mutating warmup use cases and queue-failure transitions.
- `service.py` is the compatibility/use-case facade and re-exports query and
  command functions under stable public names.
- `router.py` is the FastAPI presentation boundary.
- `jobs.py` is the canonical no-arg RQ handler entrypoint. It creates the worker
  id, opens `SessionLocal`, and delegates processing through the module worker
  and dispatcher facades.

## Legacy Compatibility Paths

These paths remain import-compatible wrappers:

```text
app.services.warmup
app.services.warmup_worker
app.services.warmup_dispatch
app.services.warmup_isolation
app.services.warmup_readiness
app.services.warmup_p2p
app.workers.warmup_jobs
app.workers.warmup_dispatch_jobs
```

These files delegate to `app.modules.warmup`. `app.modules.warmup` must not
import `app.services.warmup*` or `app.workers.warmup*`.

## Workflow Registry Integration

Warmup enqueue helpers in `app.job_queue.rq` delegate to `enqueue_workflow()`
with existing deterministic job ids:

| Workflow type | Queue | Job id | Args mode |
| --- | --- | --- | --- |
| `warmup_due_sessions` | `warmup_jobs` | `warmup-due-sessions` | `NONE` |
| `warmup_dispatch_tick` | `warmup_dispatch_jobs` | `warmup-dispatch-tick` | `NONE` |

The old helper names remain available for callers.

## No-Arg Warmup Handlers

Warmup RQ handlers must remain no-arg functions:

```text
app.modules.warmup.jobs:run_warmup_due_sessions
app.modules.warmup.jobs:run_warmup_dispatch_tick
```

The workflow registry uses `WorkflowArgsMode.NONE`, so enqueueing produces
`args=()`. Do not add a `job_id` parameter to these handlers.

## Execution Modes Preserved

Warmup module splitting does not change execution mode semantics:

- dry-run remains dry-run;
- shadow remains simulation-only;
- passive remains read-oriented;
- network and advanced remain behind their existing gates;
- quiet hours, micro-session windows, `retry_after`, p2p recording, event
  payloads, and adapter close behavior remain owned by the existing warmup
  implementation.

Live TDLib behavior remains gated and must not be enabled without explicit
operator approval.

## What Must Not Change Casually

- public warmup API paths;
- workflow types `warmup_due_sessions` and `warmup_dispatch_tick`;
- queue names;
- deterministic job ids;
- no-arg handler contract;
- `WarmupSession`, `WarmupStatus`, and `WarmupExecutionMode`;
- warmup execution modes and live gates;
- event names and payload keys;
- router registration in `main.py`.
