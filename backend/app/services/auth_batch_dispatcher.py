from __future__ import annotations

from datetime import timedelta
import uuid
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.job_queue.rq import enqueue_batch_start_auth
from app.models import (
    AuthBatch,
    AuthBatchItem,
    AuthBatchItemStatus,
    AuthBatchStatus,
    utc_now,
)
from app.services.auth_batch_state import transition_batch, transition_item


ACTIVE_COMMAND_STATUSES = {AuthBatchItemStatus.STARTING}
WAITING_INPUT_STATUSES = {AuthBatchItemStatus.WAITING_CODE, AuthBatchItemStatus.WAITING_2FA}


def dispatch_once(session: Session, batch_id: str) -> int:
    batch = session.get(AuthBatch, batch_id)
    if batch is None or batch.status != AuthBatchStatus.RUNNING:
        return 0

    launched = 0
    for _ in range(batch.max_running_commands):
        item = claim_next_item(session, batch)
        if item is None:
            break
        # This project runs plain RQ workers without rq-scheduler. Delayed jobs
        # stay in ScheduledJobRegistry forever in that setup, so batch auth start
        # commands must be enqueued immediately until scheduler support exists.
        delay_seconds = 0
        if enqueue_batch_start_auth(item.id, item.attempt_count, delay_seconds=delay_seconds):
            launched += 1
        else:
            transition_item(
                item,
                AuthBatchItemStatus.FAILED,
                actor="system",
                payload={"error_code": "QUEUE_UNAVAILABLE"},
            )
            item.error_code = "QUEUE_UNAVAILABLE"
            item.error_message = "job queue is unavailable"
            item.locked_by = None
            item.lock_expires_at = None
            _fail_queued_items_for_queue_unavailable(session, batch)
            session.commit()
            break
    return launched


def _fail_queued_items_for_queue_unavailable(session: Session, batch: AuthBatch) -> None:
    for item in batch.items:
        if item.status != AuthBatchItemStatus.QUEUED:
            continue
        item.error_code = "QUEUE_UNAVAILABLE"
        item.error_message = "job queue is unavailable"
        item.locked_by = None
        item.lock_expires_at = None
        transition_item(
            item,
            AuthBatchItemStatus.FAILED,
            actor="system",
            payload={"error_code": "QUEUE_UNAVAILABLE"},
        )
    if launched_or_waiting_items_exist(batch):
        return
    if batch.status != AuthBatchStatus.FAILED:
        transition_batch(
            batch,
            AuthBatchStatus.FAILED,
            actor="system",
            payload={"error_code": "QUEUE_UNAVAILABLE"},
        )


def launched_or_waiting_items_exist(batch: AuthBatch) -> bool:
    active_or_waiting = {
        AuthBatchItemStatus.STARTING,
        AuthBatchItemStatus.WAITING_CODE,
        AuthBatchItemStatus.WAITING_2FA,
    }
    return any(item.status in active_or_waiting for item in batch.items)


def claim_next_item(session: Session, batch: AuthBatch) -> AuthBatchItem | None:
    counts: dict[str, int] = {}
    for status, count in session.execute(
        select(AuthBatchItem.status, func.count(AuthBatchItem.id))
        .where(AuthBatchItem.batch_id == batch.id)
        .group_by(AuthBatchItem.status)
    ).all():
        counts[str(status)] = int(count)
    running = sum(counts.get(str(status), counts.get(status.value, 0)) for status in ACTIVE_COMMAND_STATUSES)
    waiting = sum(counts.get(str(status), counts.get(status.value, 0)) for status in WAITING_INPUT_STATUSES)
    if running >= batch.max_running_commands:
        return None
    if waiting >= batch.max_waiting_input:
        return None
    if running + waiting >= batch.max_total_active:
        return None

    query = (
        select(AuthBatchItem)
        .where(AuthBatchItem.batch_id == batch.id)
        .where(AuthBatchItem.status == AuthBatchItemStatus.QUEUED)
        .order_by(AuthBatchItem.position)
        .limit(1)
    )
    if session.bind and session.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    item = session.execute(query).scalars().first()
    if item is None:
        return None

    result = cast(CursorResult[Any], session.execute(
        update(AuthBatchItem)
        .where(AuthBatchItem.id == item.id)
        .where(AuthBatchItem.status == AuthBatchItemStatus.QUEUED)
        .values(
            status=AuthBatchItemStatus.STARTING,
            attempt_count=AuthBatchItem.attempt_count + 1,
            locked_by=f"dispatcher-{uuid.uuid4().hex[:8]}",
            lock_expires_at=utc_now() + timedelta(minutes=5),
            updated_at=utc_now(),
        )
    ))
    if result.rowcount != 1:
        session.rollback()
        return None
    session.commit()
    session.refresh(item)
    return item
