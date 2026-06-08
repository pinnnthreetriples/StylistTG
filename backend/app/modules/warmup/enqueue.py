from __future__ import annotations

from app.job_queue import workflows


WARMUP_DUE_SESSIONS_JOB_ID = "warmup-due-sessions"
WARMUP_DISPATCH_TICK_JOB_ID = "warmup-dispatch-tick"
WARMUP_IDLE_SWEEP_JOB_ID = "warmup-idle-sweep"


def enqueue_warmup_due_sessions() -> bool:
    return workflows.enqueue_workflow(
        workflow_type="warmup_due_sessions",
        job_id=WARMUP_DUE_SESSIONS_JOB_ID,
    )


def enqueue_warmup_dispatch_tick() -> bool:
    return workflows.enqueue_workflow(
        workflow_type="warmup_dispatch_tick",
        job_id=WARMUP_DISPATCH_TICK_JOB_ID,
    )


def enqueue_warmup_idle_sweep() -> bool:
    return workflows.enqueue_workflow(
        workflow_type="warmup_idle_sweep",
        job_id=WARMUP_IDLE_SWEEP_JOB_ID,
    )


__all__ = [
    "WARMUP_DISPATCH_TICK_JOB_ID",
    "WARMUP_DUE_SESSIONS_JOB_ID",
    "WARMUP_IDLE_SWEEP_JOB_ID",
    "enqueue_warmup_dispatch_tick",
    "enqueue_warmup_due_sessions",
    "enqueue_warmup_idle_sweep",
]
