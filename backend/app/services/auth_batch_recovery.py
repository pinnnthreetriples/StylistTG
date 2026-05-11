from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuthBatch, AuthBatchItem, AuthBatchItemStatus, AuthBatchStatus, utc_now
from app.services.auth_batch_dispatcher import dispatch_once
from app.services.auth_batch_state import transition_item

MAX_ATTEMPTS = 2


def recover_auth_batches(session: Session) -> int:
    changed = release_expired_locks(session)
    changed += expire_waiting_inputs(session)
    running_batches = list(
        session.execute(
            select(AuthBatch).where(AuthBatch.status == AuthBatchStatus.RUNNING)
        ).scalars()
    )
    for batch in running_batches:
        changed += dispatch_once(session, batch.id)
    return changed


def release_expired_locks(session: Session) -> int:
    now = utc_now()
    items = list(
        session.execute(
            select(AuthBatchItem)
            .where(AuthBatchItem.status == AuthBatchItemStatus.STARTING)
            .where(AuthBatchItem.lock_expires_at.is_not(None))
            .where(AuthBatchItem.lock_expires_at < now)
        ).scalars()
    )
    for item in items:
        item.locked_by = None
        item.lock_expires_at = None
        if item.attempt_count < MAX_ATTEMPTS:
            transition_item(
                item, AuthBatchItemStatus.QUEUED, actor="system", payload={"reason": "lock_expired"}
            )
        else:
            transition_item(
                item,
                AuthBatchItemStatus.TIMED_OUT,
                actor="system",
                payload={"reason": "lock_expired"},
            )
    session.commit()
    return len(items)


def expire_waiting_inputs(session: Session, *, timeout_seconds: int = 180) -> int:
    cutoff = utc_now() - timedelta(seconds=timeout_seconds)
    items = list(
        session.execute(
            select(AuthBatchItem)
            .where(
                AuthBatchItem.status.in_(
                    [AuthBatchItemStatus.WAITING_CODE, AuthBatchItemStatus.WAITING_2FA]
                )
            )
            .where(AuthBatchItem.updated_at < cutoff)
        ).scalars()
    )
    for item in items:
        transition_item(
            item, AuthBatchItemStatus.TIMED_OUT, actor="system", payload={"reason": "input_timeout"}
        )
    session.commit()
    return len(items)
