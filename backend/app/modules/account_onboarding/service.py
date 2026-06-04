from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountOnboardingArtifact,
    AccountOnboardingBatch,
    AccountOnboardingItem,
    AuthBatchItem,
    AuthBatchItemStatus,
    IdempotencyKey,
    new_id,
    utc_now,
)
from app.modules.account_onboarding.adapters import adapters, get_adapter
from app.modules.account_onboarding.artifacts import (
    delete_private_artifact_bytes,
    decode_upload,
    store_private_artifact,
)
from app.modules.account_onboarding.contracts import (
    AccountOnboardingArtifactCreate,
    AccountOnboardingArtifactRead,
    AccountOnboardingBatchCreate,
    AccountOnboardingBatchRead,
    AccountOnboardingCodeRequest,
    AccountOnboardingConfirmRequest,
    AccountOnboardingCountersRead,
    AccountOnboardingItemRead,
    AccountOnboardingMutationRequest,
    AccountOnboardingPasswordRequest,
    AccountOnboardingSnapshotRead,
    AccountOnboardingValidateRequest,
    OnboardingCapabilityRead,
)
from app.modules.account_onboarding.errors import (
    OnboardingError,
    artifact_not_found,
    artifact_unusable,
    batch_not_found,
    consent_required,
    invalid_state,
    item_not_found,
    queue_unavailable,
    rate_limited,
    unsupported_source,
)
from app.modules.account_onboarding.state import (
    event,
    maybe_finish_batch,
    recalculate_batch_counters,
    transition_batch,
    transition_item,
)
from app.services.auth_batch_tdlib import submit_batch_code, submit_batch_password
from app.services.auth_batches import PhoneInput, create_auth_batch, start_batch
from app.services.retry_policy import classify_error_category, retry_policy_for


MAX_ONBOARDING_RETRY_ATTEMPTS = 3
EXPIRABLE_ARTIFACT_STATUSES = {"uploaded", "quarantined", "validated", "rejected"}
USABLE_ARTIFACT_STATUSES = {"uploaded", "quarantined", "validated"}
CLEANUP_ARTIFACT_STATUSES = {"expired", "cancelled", "rejected"}


def capability_matrix() -> list[OnboardingCapabilityRead]:
    return [adapter.capability() for adapter in adapters()]


def create_batch(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    payload: AccountOnboardingBatchCreate,
) -> tuple[AccountOnboardingSnapshotRead, bool]:
    body = payload.model_dump(mode="json")
    if body["source_type"] == "phone":
        body["source_type"] = "phone_bulk"
    if body["source_type"] not in {adapter.source_type for adapter in adapters()}:
        raise unsupported_source(str(body["source_type"]))
    digest = _payload_hash(body)
    cached = _load_idempotent(
        session, workspace_id, "create_batch", payload.idempotency_key, digest
    )
    if cached:
        return AccountOnboardingSnapshotRead.model_validate(cached), False
    artifact = None
    if body.get("artifact_id"):
        artifact = _require_usable_artifact(
            session,
            workspace_id=workspace_id,
            artifact_id=str(body["artifact_id"]),
            source_type=str(body["source_type"]),
        )
    batch = AccountOnboardingBatch(
        id=new_id(),
        workspace_id=workspace_id,
        created_by_user_id=user_id,
        source_type=body["source_type"],
        label=payload.label,
        idempotency_key=payload.idempotency_key,
        payload_hash=digest,
        status="created",
    )
    session.add(batch)
    session.flush()
    if artifact is not None:
        artifact.batch_id = batch.id
        artifact.updated_at = utc_now()
    _add_preview_items(session, batch, body)
    session.flush()
    if batch.source_type == "phone_bulk":
        _ensure_phone_auth_batch(session, batch, user_id=user_id)
    recalculate_batch_counters(batch)
    event(
        batch,
        "batch.created",
        actor_user_id=user_id,
        actor_type="user",
        payload={"source_type": batch.source_type},
    )
    if body.get("artifact_id"):
        transition_batch(
            batch,
            "uploaded",
            actor_user_id=user_id,
            actor_type="user",
            payload={"artifact_id": body.get("artifact_id")},
        )
    snapshot = snapshot_read(batch)
    _save_idempotent(
        session,
        workspace_id,
        "create_batch",
        payload.idempotency_key,
        digest,
        batch.id,
        snapshot.model_dump(mode="json"),
    )
    session.commit()
    return snapshot, True


def list_batches(session: Session, *, workspace_id: str) -> list[AccountOnboardingBatchRead]:
    return [
        batch_read(row)
        for row in session.execute(
            select(AccountOnboardingBatch)
            .where(AccountOnboardingBatch.workspace_id == workspace_id)
            .order_by(AccountOnboardingBatch.created_at.desc())
        ).scalars()
    ]


def get_snapshot(
    session: Session, *, workspace_id: str, batch_id: str
) -> AccountOnboardingSnapshotRead:
    batch = _require_batch(session, workspace_id, batch_id)
    _sync_batch_from_auth(session, batch)
    session.commit()
    return snapshot_read(batch)


def validate_batch(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    batch_id: str,
    payload: AccountOnboardingValidateRequest,
) -> AccountOnboardingSnapshotRead:
    batch = _require_batch(session, workspace_id, batch_id)
    digest = _payload_hash({"batch_id": batch_id})
    cached = _load_idempotent(
        session, workspace_id, "validate_batch", payload.idempotency_key, digest
    )
    if cached:
        return AccountOnboardingSnapshotRead.model_validate(cached)
    _ensure_batch_artifacts_still_usable(session, batch)
    _sync_batch_from_auth(session, batch)
    transition_batch(batch, "validating", actor_user_id=user_id, actor_type="user")
    for item in batch.items:
        transition_item(item, "validating", actor_user_id=user_id, actor_type="user")
        transition_item(item, _target_status(item), actor_user_id=user_id, actor_type="user")
    transition_batch(batch, "preview_ready", actor_user_id=user_id, actor_type="user")
    _mark_attached_artifacts_after_validation(session, batch)
    recalculate_batch_counters(batch)
    snapshot = snapshot_read(batch)
    _save_idempotent(
        session,
        workspace_id,
        "validate_batch",
        payload.idempotency_key,
        digest,
        batch.id,
        snapshot.model_dump(mode="json"),
    )
    session.commit()
    return snapshot


def confirm_batch(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    batch_id: str,
    payload: AccountOnboardingConfirmRequest,
) -> AccountOnboardingSnapshotRead:
    batch = _require_batch(session, workspace_id, batch_id)
    _sync_batch_from_auth(session, batch)
    if not payload.consent_accepted:
        raise consent_required()
    digest = _payload_hash(payload.model_dump(mode="json"))
    cached = _load_idempotent(
        session, workspace_id, "confirm_batch", payload.idempotency_key, digest
    )
    if cached:
        return AccountOnboardingSnapshotRead.model_validate(cached)
    if batch.status != "preview_ready":
        raise invalid_state("Batch must be preview_ready before confirm.")
    batch.consent_confirmed_at = utc_now()
    batch.consent_actor_user_id = user_id
    batch.consent_version = payload.consent_version
    transition_batch(batch, "confirmed", actor_user_id=user_id, actor_type="user")
    transition_batch(batch, "queued", actor_user_id=user_id, actor_type="user")
    queued = 0
    for item in batch.items:
        if item.status == "valid":
            transition_item(item, "queued", actor_user_id=user_id, actor_type="user")
            queued += 1
    if queued == 0:
        maybe_finish_batch(batch)
    elif not enqueue_batch_items(batch):
        for item in batch.items:
            if item.status == "queued":
                item.last_error_code = "queue_unavailable"
                item.last_error_message = "Account onboarding queue is unavailable."
                transition_item(
                    item,
                    "failed",
                    actor_user_id=user_id,
                    actor_type="system",
                    payload={"reason": "queue_unavailable"},
                )
        batch.failure_code = "queue_unavailable"
        batch.failure_message = "Account onboarding queue is unavailable."
        transition_batch(batch, "failed")
        session.commit()
        raise queue_unavailable()
    snapshot = snapshot_read(batch)
    _save_idempotent(
        session,
        workspace_id,
        "confirm_batch",
        payload.idempotency_key,
        digest,
        batch.id,
        snapshot.model_dump(mode="json"),
    )
    session.commit()
    return snapshot


def cancel_batch(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    batch_id: str,
    payload: AccountOnboardingMutationRequest,
) -> AccountOnboardingSnapshotRead:
    batch = _require_batch(session, workspace_id, batch_id)
    _sync_batch_from_auth(session, batch)
    digest = _payload_hash({"batch_id": batch_id})
    cached = _load_idempotent(
        session, workspace_id, "cancel_batch", payload.idempotency_key, digest
    )
    if cached:
        return AccountOnboardingSnapshotRead.model_validate(cached)
    for item in batch.items:
        if item.status not in {
            "ready",
            "failed",
            "cancelled",
            "duplicate",
            "existing",
            "unsupported",
            "blocked",
            "requires_reauth",
        }:
            transition_item(item, "cancelled", actor_user_id=user_id, actor_type="user")
    transition_batch(batch, "cancelled", actor_user_id=user_id, actor_type="user")
    snapshot = snapshot_read(batch)
    _save_idempotent(
        session,
        workspace_id,
        "cancel_batch",
        payload.idempotency_key,
        digest,
        batch.id,
        snapshot.model_dump(mode="json"),
    )
    session.commit()
    return snapshot


def retry_item(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    batch_id: str,
    item_id: str,
    payload: AccountOnboardingMutationRequest,
) -> AccountOnboardingItemRead:
    item = _require_item(session, workspace_id, batch_id, item_id)
    _sync_item_from_auth(session, item)
    digest = _payload_hash({"batch_id": batch_id, "item_id": item_id})
    cached = _load_idempotent(session, workspace_id, "retry_item", payload.idempotency_key, digest)
    if cached:
        return AccountOnboardingItemRead.model_validate(cached)
    if item.status not in {"failed", "requires_reauth"}:
        raise invalid_state("Only failed or requires_reauth items can be retried.")
    now = utc_now()
    if item.next_retry_at and item.next_retry_at > now:
        retry_after = max(1, int((item.next_retry_at - now).total_seconds()))
        raise rate_limited(retry_after)
    attempt = item.retry_count + 1
    if attempt > MAX_ONBOARDING_RETRY_ATTEMPTS:
        raise invalid_state("Retry limit reached.")
    category = classify_error_category(item.last_error_code or item.validation_code)
    policy = retry_policy_for(category, job_type="account_onboarding", attempt=attempt)
    if not policy.retry and attempt > 1:
        raise invalid_state("Retry policy does not allow another attempt.")
    item.retry_count += 1
    if policy.interval_seconds:
        index = min(item.retry_count - 1, len(policy.interval_seconds) - 1)
        item.next_retry_at = utc_now() + timedelta(seconds=policy.interval_seconds[index])
    transition_item(item, "queued", actor_user_id=user_id, actor_type="user")
    if not enqueue_batch_items(item.batch):
        item.last_error_code = "queue_unavailable"
        item.last_error_message = "Account onboarding queue is unavailable."
        transition_item(
            item,
            "failed",
            actor_user_id=user_id,
            actor_type="system",
            payload={"reason": "queue_unavailable"},
        )
        session.commit()
        raise queue_unavailable()
    read = item_read(item)
    _save_idempotent(
        session,
        workspace_id,
        "retry_item",
        payload.idempotency_key,
        digest,
        item.id,
        read.model_dump(mode="json"),
    )
    session.commit()
    return read


def submit_code(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    batch_id: str,
    item_id: str,
    payload: AccountOnboardingCodeRequest,
) -> AccountOnboardingItemRead:
    item = _require_item(session, workspace_id, batch_id, item_id)
    _sync_item_from_auth(session, item)
    digest = _payload_hash(
        {"batch_id": batch_id, "item_id": item_id, "code_sha256": _secret_hash(payload.code)}
    )
    cached = _load_idempotent(session, workspace_id, "submit_code", payload.idempotency_key, digest)
    if cached:
        return AccountOnboardingItemRead.model_validate(cached)
    if item.status != "waiting_code":
        raise invalid_state("Item is not waiting for code.")
    event(
        item.batch,
        "item.code_received",
        item=item,
        actor_user_id=user_id,
        actor_type="user",
        payload={"code": "[redacted]"},
    )
    if item.auth_batch_item_id is None:
        raise invalid_state("Item is not linked to an auth batch item.")
    try:
        auth_item = submit_batch_code(session, item.auth_batch_item_id, payload.code)
    except ValueError as exc:
        raise invalid_state(str(exc)) from exc
    if auth_item.batch.status == "running":
        from app.services.auth_batch_dispatcher import dispatch_once

        dispatch_once(session, auth_item.batch_id)
    _apply_auth_item_to_onboarding_item(item, auth_item)
    maybe_finish_batch(item.batch)
    read = item_read(item)
    _save_idempotent(
        session,
        workspace_id,
        "submit_code",
        payload.idempotency_key,
        digest,
        item.id,
        read.model_dump(mode="json"),
    )
    session.commit()
    return read


def submit_password(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    batch_id: str,
    item_id: str,
    payload: AccountOnboardingPasswordRequest,
) -> AccountOnboardingItemRead:
    item = _require_item(session, workspace_id, batch_id, item_id)
    _sync_item_from_auth(session, item)
    digest = _payload_hash(
        {
            "batch_id": batch_id,
            "item_id": item_id,
            "password_sha256": _secret_hash(payload.password),
        }
    )
    cached = _load_idempotent(
        session, workspace_id, "submit_password", payload.idempotency_key, digest
    )
    if cached:
        return AccountOnboardingItemRead.model_validate(cached)
    if item.status != "waiting_2fa":
        raise invalid_state("Item is not waiting for 2FA password.")
    event(
        item.batch,
        "item.password_received",
        item=item,
        actor_user_id=user_id,
        actor_type="user",
        payload={"password": "[redacted]"},
    )
    if item.auth_batch_item_id is None:
        raise invalid_state("Item is not linked to an auth batch item.")
    try:
        auth_item = submit_batch_password(session, item.auth_batch_item_id, payload.password)
    except ValueError as exc:
        raise invalid_state(str(exc)) from exc
    if auth_item.batch.status == "running":
        from app.services.auth_batch_dispatcher import dispatch_once

        dispatch_once(session, auth_item.batch_id)
    _apply_auth_item_to_onboarding_item(item, auth_item)
    maybe_finish_batch(item.batch)
    read = item_read(item)
    _save_idempotent(
        session,
        workspace_id,
        "submit_password",
        payload.idempotency_key,
        digest,
        item.id,
        read.model_dump(mode="json"),
    )
    session.commit()
    return read


def upload_artifact(
    session: Session,
    *,
    workspace_id: str,
    user_id: str | None,
    payload: AccountOnboardingArtifactCreate,
) -> tuple[AccountOnboardingArtifactRead, bool]:
    data = decode_upload(payload.content_base64)
    digest = _payload_hash(
        {
            "source_type": payload.source_type,
            "filename": payload.filename,
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )
    cached = _load_idempotent(
        session, workspace_id, "upload_artifact", payload.idempotency_key, digest
    )
    if cached:
        return AccountOnboardingArtifactRead.model_validate(cached), False
    artifact_id = new_id()
    stored = store_private_artifact(
        workspace_id=workspace_id,
        artifact_id=artifact_id,
        filename=payload.filename,
        source_type=payload.source_type,
        data=data,
    )
    artifact = AccountOnboardingArtifact(
        id=artifact_id,
        workspace_id=workspace_id,
        source_type=payload.source_type,
        object_key=stored.object_key,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        content_type_detected=stored.content_type_detected,
        status="quarantined",
        created_by_user_id=user_id,
        expires_at=utc_now() + timedelta(days=7),
    )
    session.add(artifact)
    session.flush()
    read = artifact_read(artifact)
    _save_idempotent(
        session,
        workspace_id,
        "upload_artifact",
        payload.idempotency_key,
        digest,
        artifact.id,
        read.model_dump(mode="json"),
    )
    session.commit()
    return read, True


def expire_artifacts(session: Session, *, workspace_id: str | None = None, limit: int = 100) -> int:
    query = (
        select(AccountOnboardingArtifact)
        .where(
            AccountOnboardingArtifact.status.in_(EXPIRABLE_ARTIFACT_STATUSES),
            AccountOnboardingArtifact.expires_at <= utc_now(),
        )
        .order_by(AccountOnboardingArtifact.expires_at.asc())
        .limit(limit)
    )
    if workspace_id is not None:
        query = query.where(AccountOnboardingArtifact.workspace_id == workspace_id)
    rows = list(session.execute(query).scalars())
    for artifact in rows:
        artifact.status = "expired"
        artifact.updated_at = utc_now()
        artifact.failure_code = artifact.failure_code or "artifact_expired"
        artifact.failure_message = (
            artifact.failure_message
            or "Account onboarding artifact expired before materialization."
        )
        if artifact.batch is not None:
            event(
                artifact.batch,
                "artifact.expired",
                actor_type="system",
                payload={"artifact_id": artifact.id, "source_type": artifact.source_type},
            )
    session.commit()
    return len(rows)


def cleanup_artifact_files(
    session: Session, *, workspace_id: str | None = None, limit: int = 100
) -> int:
    query = (
        select(AccountOnboardingArtifact)
        .where(AccountOnboardingArtifact.status.in_(CLEANUP_ARTIFACT_STATUSES))
        .order_by(AccountOnboardingArtifact.updated_at.asc())
        .limit(limit)
    )
    if workspace_id is not None:
        query = query.where(AccountOnboardingArtifact.workspace_id == workspace_id)
    rows = list(session.execute(query).scalars())
    deleted = 0
    for artifact in rows:
        try:
            removed = delete_private_artifact_bytes(artifact.object_key)
        except ValueError:
            artifact.failure_code = "artifact_cleanup_unsafe_key"
            artifact.failure_message = "Artifact object key is outside the private namespace."
            artifact.updated_at = utc_now()
            continue
        if not removed:
            continue
        artifact.status = "deleted"
        artifact.failure_code = artifact.failure_code or "artifact_bytes_deleted"
        artifact.failure_message = (
            artifact.failure_message or "Private artifact bytes were deleted."
        )
        artifact.updated_at = utc_now()
        deleted += 1
        if artifact.batch is not None:
            event(
                artifact.batch,
                "artifact.bytes_deleted",
                actor_type="system",
                payload={"artifact_id": artifact.id, "source_type": artifact.source_type},
            )
    session.commit()
    return deleted


def execute_item(session: Session, *, item_id: str) -> AccountOnboardingItem:
    item = session.get(AccountOnboardingItem, item_id)
    if item is None:
        raise item_not_found()
    if item.batch.consent_confirmed_at is None:
        raise consent_required()
    if item.status != "queued":
        _sync_item_from_auth(session, item)
        return item
    transition_batch(item.batch, "running")
    if item.batch.source_type == "phone_bulk":
        _start_phone_auth(session, item)
        session.commit()
        return item
    adapter = get_adapter(item.batch.source_type)
    outcome = adapter.execute(item)
    if item.batch.source_type == "phone_bulk":
        item.last_error_code = outcome.code
        item.last_error_message = outcome.message
        transition_item(item, outcome.status, payload=outcome.payload or {"outcome": outcome.code})
    elif item.batch.source_type == "tdlib_directory":
        transition_item(item, "checking_session")
        item.last_error_code = outcome.code
        item.last_error_message = outcome.message
        transition_item(
            item, outcome.status, payload={"verification": outcome.code, **(outcome.payload or {})}
        )
    else:
        item.last_error_code = outcome.code
        item.last_error_message = outcome.message
        transition_item(
            item, outcome.status, payload={"outcome": outcome.code, **(outcome.payload or {})}
        )
    maybe_finish_batch(item.batch)
    session.commit()
    return item


def enqueue_batch_items(batch: AccountOnboardingBatch) -> bool:
    from app.job_queue.rq import enqueue_account_onboarding_item

    ok = True
    for item in batch.items:
        if item.status == "queued":
            ok = enqueue_account_onboarding_item(item.id, item.retry_count) and ok
    return ok


def snapshot_read(batch: AccountOnboardingBatch) -> AccountOnboardingSnapshotRead:
    return AccountOnboardingSnapshotRead(
        batch=batch_read(batch),
        items=[item_read(item) for item in batch.items],
        capabilities=capability_matrix(),
        poll_again_in_ms=2500
        if batch.status in {"queued", "running", "partially_completed"}
        else 0,
        next_action="confirm" if batch.status == "preview_ready" else None,
    )


def batch_read(batch: AccountOnboardingBatch) -> AccountOnboardingBatchRead:
    return AccountOnboardingBatchRead(
        id=batch.id,
        source_type=batch.source_type,
        status=batch.status,
        label=batch.label,
        counters=AccountOnboardingCountersRead(
            total_count=batch.total_count,
            valid_count=batch.valid_count,
            ready_count=batch.ready_count,
            failed_count=batch.failed_count,
            blocked_count=batch.blocked_count,
            requires_reauth_count=batch.requires_reauth_count,
        ),
        created_at=_as_aware(batch.created_at),
        updated_at=_as_aware(batch.updated_at),
        consent_confirmed_at=_as_optional_aware(batch.consent_confirmed_at),
        confirmed_at=_as_optional_aware(batch.confirmed_at),
        queued_at=_as_optional_aware(batch.queued_at),
        started_at=_as_optional_aware(batch.started_at),
        completed_at=_as_optional_aware(batch.completed_at),
        cancelled_at=_as_optional_aware(batch.cancelled_at),
        failure_code=batch.failure_code,
        failure_message=batch.failure_message,
    )


def item_read(item: AccountOnboardingItem) -> AccountOnboardingItemRead:
    next_action = (
        "submit_code"
        if item.status == "waiting_code"
        else "submit_password"
        if item.status == "waiting_2fa"
        else "retry"
        if item.status in {"failed", "requires_reauth"}
        else None
    )
    return AccountOnboardingItemRead(
        id=item.id,
        batch_id=item.batch_id,
        account_id=item.account_id,
        auth_session_id=item.auth_session_id,
        source_type=item.batch.source_type,
        position=item.position,
        status=item.status,
        phone_hint=item.phone_hint,
        username_hint=item.username_hint,
        telegram_user_id_hint=item.telegram_user_id_hint,
        label=item.label,
        validation_code=item.validation_code,
        validation_message=item.validation_message,
        risk_level=item.risk_level,
        requires_reauth=item.requires_reauth,
        last_error_code=item.last_error_code,
        last_error_message=item.last_error_message,
        created_at=_as_aware(item.created_at),
        updated_at=_as_aware(item.updated_at),
        next_retry_at=_as_optional_aware(item.next_retry_at),
        next_action=next_action,
    )


def artifact_read(artifact: AccountOnboardingArtifact) -> AccountOnboardingArtifactRead:
    return AccountOnboardingArtifactRead(
        id=artifact.id,
        source_type=artifact.source_type,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        content_type_detected=artifact.content_type_detected,
        status=artifact.status,
        created_at=_as_aware(artifact.created_at),
        expires_at=_as_aware(artifact.expires_at),
        failure_code=artifact.failure_code,
        failure_message=artifact.failure_message,
    )


def _add_preview_items(
    session: Session, batch: AccountOnboardingBatch, body: dict[str, Any]
) -> None:
    previews = get_adapter(batch.source_type).preview(
        session, workspace_id=batch.workspace_id, body=body
    )
    for preview in previews:
        row = preview.to_row()
        now = utc_now()
        session.add(
            AccountOnboardingItem(
                workspace_id=batch.workspace_id,
                batch_id=batch.id,
                source_ref_hash=_hash(row["source_ref"]),
                position=row["position"],
                status="pending",
                phone_number=row.get("phone"),
                phone_hint=row.get("phone_hint"),
                phone_normalized_hash=_hash(row["phone"]) if row.get("phone") else None,
                username_hint=row.get("username_hint"),
                telegram_user_id_hint=row.get("telegram_user_id_hint"),
                label=row.get("label"),
                validation_code=row.get("validation_code"),
                validation_message=row.get("validation_message"),
                risk_level=row.get("risk_level", "low"),
                requires_reauth=row.get("requires_reauth", False),
                account_id=row.get("account_id"),
                artifact_id=row.get("artifact_id"),
                created_at=now,
                updated_at=now,
            )
        )


def _ensure_phone_auth_batch(
    session: Session, batch: AccountOnboardingBatch, *, user_id: str | None
) -> None:
    valid_items = [
        item for item in batch.items if item.validation_code is None and item.phone_number
    ]
    if not valid_items:
        return
    inputs = [
        PhoneInput(phone_number=str(item.phone_number), label=item.label) for item in valid_items
    ]
    auth_batch, _created = create_auth_batch(
        session,
        idempotency_key=f"account-onboarding:{batch.id}",
        label=batch.label,
        inputs=inputs,
        workspace_id=batch.workspace_id,
        actor_user_id=user_id,
    )
    auth_by_phone_hash = {
        _hash(auth_item.phone_number): auth_item for auth_item in auth_batch.items
    }
    for item in valid_items:
        auth_item = auth_by_phone_hash.get(item.phone_normalized_hash or "")
        if auth_item is None:
            continue
        item.auth_batch_id = auth_batch.id
        item.auth_batch_item_id = auth_item.id
        item.account_id = auth_item.account_id


def _start_phone_auth(session: Session, item: AccountOnboardingItem) -> None:
    if item.auth_batch_id is None or item.auth_batch_item_id is None:
        _ensure_phone_auth_batch(session, item.batch, user_id=item.batch.created_by_user_id)
    if item.auth_batch_id is None or item.auth_batch_item_id is None:
        item.last_error_code = "phone_auth_bridge_missing"
        item.last_error_message = "Phone onboarding item is not linked to auth execution."
        transition_item(item, "failed", payload={"reason": "phone_auth_bridge_missing"})
        maybe_finish_batch(item.batch)
        return
    auth_batch = start_batch(session, item.auth_batch_id, workspace_id=item.workspace_id)
    from app.services.auth_batch_dispatcher import dispatch_once

    launched = dispatch_once(session, auth_batch.id)
    auth_item = session.get(AuthBatchItem, item.auth_batch_item_id)
    if auth_item is None:
        item.last_error_code = "phone_auth_item_missing"
        item.last_error_message = "Linked auth batch item was not found."
        transition_item(item, "failed", payload={"reason": "phone_auth_item_missing"})
        maybe_finish_batch(item.batch)
        return
    if launched == 0 and auth_item.status == AuthBatchItemStatus.QUEUED:
        item.last_error_code = "phone_auth_dispatch_not_started"
        item.last_error_message = "Phone auth worker dispatch did not start."
        transition_item(item, "failed", payload={"reason": "phone_auth_dispatch_not_started"})
        maybe_finish_batch(item.batch)
        return
    _apply_auth_item_to_onboarding_item(item, auth_item)


def _sync_batch_from_auth(session: Session | None, batch: AccountOnboardingBatch) -> None:
    for item in batch.items:
        _sync_item_from_auth(session, item)
    maybe_finish_batch(batch)


def _sync_item_from_auth(session: Session | None, item: AccountOnboardingItem) -> None:
    if item.auth_batch_item_id is None:
        return
    auth_item = (
        session.get(AuthBatchItem, item.auth_batch_item_id) if session else item.auth_batch_item
    )
    if auth_item is None:
        return
    _apply_auth_item_to_onboarding_item(item, auth_item)


def _apply_auth_item_to_onboarding_item(
    item: AccountOnboardingItem, auth_item: AuthBatchItem
) -> None:
    target = _onboarding_status_for_auth_item(auth_item)
    item.account_id = auth_item.account_id
    item.last_error_code = auth_item.error_code
    item.last_error_message = auth_item.error_message
    if target == item.status:
        return
    if item.status == "queued" and target in {
        "starting_auth",
        "waiting_code",
        "waiting_2fa",
        "ready",
    }:
        transition_item(item, "starting_auth", payload={"auth_batch_item_id": auth_item.id})
    if item.status == "starting_auth" and target in {"waiting_code", "waiting_2fa", "ready"}:
        transition_item(item, target, payload={"auth_batch_item_id": auth_item.id})
    elif target in {"failed", "cancelled"}:
        transition_item(item, target, payload={"auth_batch_item_id": auth_item.id})
    elif item.status in {"waiting_code", "waiting_2fa"} and target in {
        "waiting_2fa",
        "ready",
        "failed",
    }:
        transition_item(item, target, payload={"auth_batch_item_id": auth_item.id})


def _onboarding_status_for_auth_item(auth_item: AuthBatchItem) -> str:
    if auth_item.status == AuthBatchItemStatus.QUEUED:
        return "queued"
    if auth_item.status == AuthBatchItemStatus.STARTING:
        return "starting_auth"
    if auth_item.status == AuthBatchItemStatus.WAITING_CODE:
        return "waiting_code"
    if auth_item.status == AuthBatchItemStatus.WAITING_2FA:
        return "waiting_2fa"
    if auth_item.status == AuthBatchItemStatus.AUTHORIZED:
        return "ready"
    if auth_item.status == AuthBatchItemStatus.CANCELLED:
        return "cancelled"
    return "failed"


def _target_status(item: AccountOnboardingItem) -> str:
    if item.validation_code == "duplicate":
        return "duplicate"
    if item.validation_code == "existing_account":
        return "existing"
    if item.validation_code in {
        "phone_invalid",
        "active_conflict",
        "artifact_missing",
        "metadata_invalid",
    }:
        return "blocked"
    if item.validation_code == "session_file_unsupported":
        return "unsupported"
    if item.requires_reauth:
        return "requires_reauth"
    return "valid"


def _require_batch(session: Session, workspace_id: str, batch_id: str) -> AccountOnboardingBatch:
    batch = session.get(AccountOnboardingBatch, batch_id)
    if batch is None or batch.workspace_id != workspace_id:
        raise batch_not_found()
    return batch


def _require_item(
    session: Session, workspace_id: str, batch_id: str, item_id: str
) -> AccountOnboardingItem:
    item = session.get(AccountOnboardingItem, item_id)
    if item is None or item.workspace_id != workspace_id or item.batch_id != batch_id:
        raise item_not_found()
    return item


def _require_usable_artifact(
    session: Session,
    *,
    workspace_id: str,
    artifact_id: str,
    source_type: str,
    expected_batch_id: str | None = None,
) -> AccountOnboardingArtifact:
    artifact = session.get(AccountOnboardingArtifact, artifact_id)
    if artifact is None or artifact.workspace_id != workspace_id:
        raise artifact_not_found()
    if artifact.batch_id is not None and artifact.batch_id != expected_batch_id:
        raise artifact_unusable(
            "artifact_already_attached",
            "Artifact is already attached to another onboarding batch.",
        )
    if artifact.source_type != source_type:
        raise artifact_unusable(
            "artifact_source_mismatch",
            "Artifact source type does not match the onboarding source.",
        )
    if _as_aware(artifact.expires_at) <= utc_now():
        raise artifact_unusable("artifact_expired", "Artifact has expired.")
    if artifact.status not in USABLE_ARTIFACT_STATUSES:
        raise artifact_unusable(
            "artifact_status_unusable",
            "Artifact is not in a usable upload state.",
        )
    return artifact


def _mark_attached_artifacts_after_validation(
    session: Session, batch: AccountOnboardingBatch
) -> None:
    artifact_ids = {item.artifact_id for item in batch.items if item.artifact_id}
    if not artifact_ids:
        return
    failed_artifact_ids = {
        item.artifact_id
        for item in batch.items
        if item.artifact_id and item.status in {"blocked", "unsupported", "failed"}
    }
    rows = session.execute(
        select(AccountOnboardingArtifact).where(
            AccountOnboardingArtifact.workspace_id == batch.workspace_id,
            AccountOnboardingArtifact.id.in_(artifact_ids),
        )
    ).scalars()
    for artifact in rows:
        if artifact.id in failed_artifact_ids:
            artifact.status = "rejected"
            artifact.failure_code = "artifact_validation_failed"
            artifact.failure_message = "Artifact failed source-specific onboarding validation."
        else:
            artifact.status = "validated"
            artifact.failure_code = None
            artifact.failure_message = None
        artifact.batch_id = batch.id
        artifact.updated_at = utc_now()


def _ensure_batch_artifacts_still_usable(session: Session, batch: AccountOnboardingBatch) -> None:
    for artifact_id in {item.artifact_id for item in batch.items if item.artifact_id}:
        _require_usable_artifact(
            session,
            workspace_id=batch.workspace_id,
            artifact_id=str(artifact_id),
            source_type=batch.source_type,
            expected_batch_id=batch.id,
        )


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _secret_hash(value: str) -> str:
    salt = os.getenv(
        "ACCOUNT_ONBOARDING_PASSWORD_HASH_SALT",
        "account-onboarding-default-salt",
    ).encode("utf-8")
    derived = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, 600_000)
    return derived.hex()


def _payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _key(operation: str, key: str) -> str:
    return f"account_onboarding:{operation}:{hashlib.sha256(key.encode('utf-8')).hexdigest()}"


def _load_idempotent(
    session: Session, workspace_id: str, operation: str, key: str, digest: str
) -> dict[str, Any] | None:
    row = session.get(IdempotencyKey, (workspace_id, _key(operation, key)))
    if row is None:
        return None
    if row.response_json.get("_payload_hash") != digest:
        raise OnboardingError(
            "ONBOARDING_INVALID_STATE",
            "Idempotency key was already used with a different payload.",
            HTTPStatus.CONFLICT,
            "Idempotency conflict",
        )
    response = dict(row.response_json)
    response.pop("_payload_hash", None)
    return response


def _save_idempotent(
    session: Session,
    workspace_id: str,
    operation: str,
    key: str,
    digest: str,
    entity_id: str,
    response: dict[str, Any],
) -> None:
    safe = dict(response)
    safe["_payload_hash"] = digest
    session.add(
        IdempotencyKey(
            workspace_id=workspace_id,
            key=_key(operation, key),
            operation=operation,
            entity_id=entity_id,
            response_json=safe,
            expires_at=utc_now() + timedelta(days=7),
        )
    )


def _as_aware(value: datetime | None) -> datetime:
    if value is None:
        return utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _as_optional_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _as_aware(value)
