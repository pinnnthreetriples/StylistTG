# Warmup Module

## Goal

`app.modules.warmup` is the canonical module boundary for Account Preparation /
Warmup workflow metadata and job entrypoints.

Phase 4 is an ownership migration, not a warmup redesign. Public API behavior,
execution modes, queues, deterministic job ids, and legacy import paths remain
stable.

## Current Phase 6 Scope

Phase 6 hardens warmup ownership after the Phase 4 wrapper-first migration:

- Workflow metadata already lives in `app.modules.warmup.module`.
- RQ handler paths point at `app.modules.warmup.jobs`.
- Existing enqueue helpers delegate through the workflow registry.
- Warmup service, events, worker, dispatcher, isolation, readiness, and p2p
  implementation bodies now live under `app.modules.warmup`.
- Legacy `app.services.warmup*` files remain import-compatible wrappers.

The phase intentionally avoids repository, policies, and typed-error extraction.

## Canonical Module Path

The canonical warmup module boundary is:

```text
backend/app/modules/warmup/
  module.py
  jobs.py
  service.py
  isolation.py
  readiness.py
  p2p.py
  worker.py
  dispatcher.py
  events.py
  router.py
```

`jobs.py` is the canonical no-arg RQ handler entrypoint. It creates the worker id,
opens `SessionLocal`, and delegates processing through the module worker and
dispatcher facades.

## Legacy Compatibility Paths

These paths remain import-compatible:

```text
app.services.warmup
app.services.warmup_worker
app.services.warmup_dispatch
app.workers.warmup_jobs
app.workers.warmup_dispatch_jobs
```

These files now delegate to `app.modules.warmup`. `app.modules.warmup` must not
import `app.services.warmup*` or `app.workers.warmup*`.

## Workflow Registry Integration

Warmup enqueue helpers in `app.job_queue.rq` now delegate to `enqueue_workflow()`
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

Phase 4 does not change execution mode semantics:

- dry-run remains dry-run;
- shadow remains simulation-only;
- passive remains read-oriented;
- network and advanced remain behind their existing gates;
- quiet hours, micro-session windows, `retry_after`, p2p recording, event
  payloads, and adapter close behavior remain owned by the existing warmup
  implementation.

Live TDLib behavior remains gated and must not be enabled without explicit
operator approval.

## Deferred Work

Later phases may split warmup internals further:

- split DB helpers into `repository.py`;
- split business checks into `policies.py`;
- add typed warmup errors in `errors.py`;
- remove legacy wrappers after call-site audits show no users.

Those phases need behavior-matching tests before any implementation move.

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
