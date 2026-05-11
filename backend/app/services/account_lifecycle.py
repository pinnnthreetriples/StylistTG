from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.models import (
    Account,
    AccountDeletionRequest,
    AccountExportRequest,
    AccountLifecycleEvent,
    Asset,
    new_id,
    utc_now,
)
from app.services.account_risk import build_account_readiness_risk
from app.services.accounts import get_account
from app.services.sensitive_audit import record_sensitive_audit_event
from app.services.secret_redaction import redact_metadata
from app.storage import StorageService, build_storage_service

ACTIVE_DELETION_STATUSES = {"requested", "approved", "queued", "running"}
EXPORT_CONTENT_TYPE = "application/json"
EXPORT_SCHEMA_VERSION = 1


def build_account_deletion_preview(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    account = _account_or_raise(session, account_id, workspace_id)
    risk = build_account_readiness_risk(session, account)
    assets = _account_assets(session, account)
    active_jobs = [
        job for job in account.jobs if job.job_state in {"queued", "running", "waiting_lock"}
    ]
    blocking_reasons = ["active_jobs"] if active_jobs else []
    return {
        "account_id": account.id,
        "can_delete": not blocking_reasons,
        "risk_level": risk["level"],
        "risk_score": risk["score"],
        "blocking_reasons": blocking_reasons,
        "planned_actions": [
            {"type": "db_rows", "resource": "account", "count": 1},
            {
                "type": "db_rows",
                "resource": "jobs",
                "count": len(account.jobs),
                "retention_policy": "retain_minimal",
            },
            {"type": "asset_objects", "resource": "account_assets", "count": len(assets)},
            {
                "type": "tdlib_session",
                "resource": "tdlib_session_dir",
                "present": bool(account.runtime_state and account.runtime_state.session_present),
            },
            {"type": "logs", "resource": "operation_logs", "retention_policy": "retain_redacted"},
            {"type": "audit", "resource": "sensitive_audit_event", "retention_policy": "retain"},
        ],
        "requires_confirmation": True,
        "generated_at": utc_now(),
    }


def request_account_deletion(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    actor_user_id: str | None,
    reason: str,
    confirmation: str,
    dry_run: bool,
    config: Settings = settings,
) -> AccountDeletionRequest:
    if confirmation != "DELETE":
        raise ValueError("confirmation required")
    if len(reason.strip()) < 10:
        raise ValueError("reason too short")
    account = _account_or_raise(session, account_id, workspace_id)
    existing = (
        session.execute(
            select(AccountDeletionRequest)
            .where(AccountDeletionRequest.account_id == account_id)
            .where(AccountDeletionRequest.status.in_(ACTIVE_DELETION_STATUSES))
            .limit(1)
        )
        .scalars()
        .first()
    )
    if existing is not None:
        raise ValueError("active deletion request exists")
    preview = build_account_deletion_preview(
        session, account_id=account_id, workspace_id=workspace_id
    )
    if not preview["can_delete"]:
        raise ValueError("deletion preview has blockers")
    status = "previewed" if dry_run or config.account_deletion_dry_run_default else "requested"
    request = AccountDeletionRequest(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account.id,
        requested_by_user_id=actor_user_id,
        status=status,
        reason=reason,
        dry_run_result_json=_json_safe(preview),
        requested_at=utc_now(),
    )
    session.add(request)
    _record_lifecycle_event(
        session,
        workspace_id=workspace_id,
        account_id=account.id,
        event_type="account.delete.requested",
        actor_user_id=actor_user_id,
        request_id=request.id,
        payload={"dry_run": dry_run, "status": status},
    )
    record_sensitive_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="account.delete.requested",
        entity_type="account_deletion_request",
        entity_id=request.id,
        account_id=account.id,
        reason=reason,
        risk_level=preview["risk_level"],
        risk_score=preview["risk_score"],
        metadata={"dry_run": dry_run, "planned_action_count": len(preview["planned_actions"])},
    )
    session.commit()
    session.refresh(request)
    return request


def list_deletion_requests(
    session: Session, *, account_id: str, workspace_id: str
) -> list[AccountDeletionRequest]:
    _account_or_raise(session, account_id, workspace_id)
    return list(
        session.execute(
            select(AccountDeletionRequest)
            .where(AccountDeletionRequest.workspace_id == workspace_id)
            .where(AccountDeletionRequest.account_id == account_id)
            .order_by(AccountDeletionRequest.requested_at.desc())
        )
        .scalars()
        .all()
    )


def get_deletion_request(
    session: Session, *, account_id: str, request_id: str, workspace_id: str
) -> AccountDeletionRequest | None:
    _account_or_raise(session, account_id, workspace_id)
    return (
        session.execute(
            select(AccountDeletionRequest)
            .where(AccountDeletionRequest.workspace_id == workspace_id)
            .where(AccountDeletionRequest.account_id == account_id)
            .where(AccountDeletionRequest.id == request_id)
            .limit(1)
        )
        .scalars()
        .first()
    )


def execute_account_deletion_request(
    session: Session,
    *,
    request_id: str,
    storage: StorageService | None = None,
    config: Settings = settings,
) -> dict[str, Any]:
    request = session.get(AccountDeletionRequest, request_id)
    if request is None:
        raise ValueError("deletion request not found")
    account = _account_or_raise(session, request.account_id, request.workspace_id)
    if not config.account_deletion_allow_hard_delete:
        result: dict[str, Any] = {
            "executed": False,
            "mode": "dry_run",
            "reason": "hard_delete_disabled",
        }
        request.execution_result_json = result
        request.status = "approved"
        session.commit()
        return result
    request.status = "running"
    request.started_at = utc_now()
    assets = _account_assets(session, account)
    storage_service = storage or build_storage_service(config)
    deleted_asset_objects = 0
    for asset in assets:
        for key in {asset.source_key, asset.normalized_key}:
            if key and storage_service.delete(key):
                deleted_asset_objects += 1
    account.account_state = "disabled"
    if account.runtime_state:
        account.runtime_state.session_present = False
        account.runtime_state.runtime_health = "deleted"
        account.runtime_state.recovery_marker = "account_deletion_completed"
    result: dict[str, Any] = {
        "executed": True,
        "account_state": "disabled",
        "asset_objects_deleted": deleted_asset_objects,
        "audit_retained": True,
        "tdlib_session_deletion": "planned_by_safe_helper",
    }
    request.status = "completed"
    request.completed_at = utc_now()
    request.execution_result_json = result
    record_sensitive_audit_event(
        session,
        workspace_id=request.workspace_id,
        actor_user_id=request.requested_by_user_id,
        action="account.delete.completed",
        entity_type="account_deletion_request",
        entity_id=request.id,
        account_id=request.account_id,
        metadata=result,
    )
    session.commit()
    return result


def create_account_export_request(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    actor_user_id: str | None,
    storage: StorageService | None = None,
    config: Settings = settings,
) -> AccountExportRequest:
    account = _account_or_raise(session, account_id, workspace_id)
    export_id = new_id()
    payload = build_account_export_payload(session, account=account)
    body = json.dumps(payload, default=str, ensure_ascii=False, indent=2).encode("utf-8")
    key = f"exports/accounts/{workspace_id}/{account_id}/{export_id}/account-export.json"
    storage_service = storage or build_storage_service(config)
    storage_service.save_bytes(key, body, content_type=EXPORT_CONTENT_TYPE)
    now = utc_now()
    request = AccountExportRequest(
        id=export_id,
        workspace_id=workspace_id,
        account_id=account_id,
        requested_by_user_id=actor_user_id,
        status="completed",
        export_key=key,
        export_size_bytes=len(body),
        export_content_type=EXPORT_CONTENT_TYPE,
        requested_at=now,
        completed_at=now,
        expires_at=now + timedelta(days=config.account_export_ttl_days),
    )
    session.add(request)
    record_sensitive_audit_event(
        session,
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        action="account.export.completed",
        entity_type="account_export_request",
        entity_id=request.id,
        account_id=account_id,
        metadata={
            "export_size_bytes": len(body),
            "export_ttl_days": config.account_export_ttl_days,
        },
    )
    session.commit()
    session.refresh(request)
    return request


def list_export_requests(
    session: Session, *, account_id: str, workspace_id: str
) -> list[AccountExportRequest]:
    _account_or_raise(session, account_id, workspace_id)
    return list(
        session.execute(
            select(AccountExportRequest)
            .where(AccountExportRequest.workspace_id == workspace_id)
            .where(AccountExportRequest.account_id == account_id)
            .order_by(AccountExportRequest.requested_at.desc())
        )
        .scalars()
        .all()
    )


def get_export_request(
    session: Session, *, account_id: str, request_id: str, workspace_id: str
) -> AccountExportRequest | None:
    _account_or_raise(session, account_id, workspace_id)
    return (
        session.execute(
            select(AccountExportRequest)
            .where(AccountExportRequest.workspace_id == workspace_id)
            .where(AccountExportRequest.account_id == account_id)
            .where(AccountExportRequest.id == request_id)
            .limit(1)
        )
        .scalars()
        .first()
    )


def build_account_export_payload(session: Session, *, account: Account) -> dict[str, Any]:
    assets = _account_assets(session, account)
    return redact_metadata(
        {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "exported_at": utc_now().isoformat(),
            "account": {
                "id": account.id,
                "workspace_id": account.workspace_id,
                "state": account.account_state,
                "telegram_user_id": account.telegram_user_id,
                "profile": _profile_payload(account),
                "risk": build_account_readiness_risk(session, account),
                "session_data": "[excluded]",
            },
            "assets": [
                {
                    "id": asset.id,
                    "kind": asset.kind,
                    "status": asset.status,
                    "mime": asset.mime,
                    "size_bytes": asset.normalized_size_bytes or asset.source_size_bytes,
                }
                for asset in assets
            ],
            "jobs": [
                {
                    "id": job.id,
                    "workflow_type": job.workflow_type,
                    "state": job.job_state,
                    "queued_at": job.queued_at,
                    "finished_at": job.finished_at,
                    "failure_reason": job.failure_reason,
                }
                for job in account.jobs
            ],
            "operation_logs": [
                {
                    "id": row.id,
                    "operation_type": row.operation_type,
                    "status": row.status,
                    "severity": row.severity,
                    "message": row.message,
                    "created_at": row.created_at,
                }
                for row in account.operation_logs
            ],
            "proxy_credentials": "[redacted]",
        }
    )


def deletion_request_to_dict(request: AccountDeletionRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "account_id": request.account_id,
        "status": request.status,
        "reason": request.reason,
        "dry_run_result": request.dry_run_result_json,
        "execution_result": request.execution_result_json,
        "requested_at": request.requested_at,
        "completed_at": request.completed_at,
        "failed_at": request.failed_at,
        "failure_code": request.failure_code,
        "failure_message": request.failure_message,
    }


def export_request_to_dict(request: AccountExportRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "account_id": request.account_id,
        "status": request.status,
        "export_key": "[private]" if request.export_key else None,
        "export_size_bytes": request.export_size_bytes,
        "export_content_type": request.export_content_type,
        "requested_at": request.requested_at,
        "completed_at": request.completed_at,
        "failed_at": request.failed_at,
        "failure_code": request.failure_code,
        "failure_message": request.failure_message,
        "expires_at": request.expires_at,
    }


def _account_or_raise(session: Session, account_id: str, workspace_id: str) -> Account:
    account = get_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    return account


def _account_assets(session: Session, account: Account) -> list[Asset]:
    asset_ids: set[str] = set()
    if account.profile_state and account.profile_state.profile_photo_asset_id:
        asset_ids.add(account.profile_state.profile_photo_asset_id)
    if account.profile_audio_state and account.profile_audio_state.source_asset_id:
        asset_ids.add(account.profile_audio_state.source_asset_id)
    asset_ids.update(draft.asset_id for draft in account.story_drafts)
    asset_ids.update(post.asset_id for post in account.story_posts if post.asset_id)
    if not asset_ids:
        return []
    return list(
        session.execute(
            select(Asset)
            .where(Asset.workspace_id == account.workspace_id)
            .where(Asset.id.in_(asset_ids))
        )
        .scalars()
        .all()
    )


def _profile_payload(account: Account) -> dict[str, Any] | None:
    profile = account.profile_state
    if profile is None:
        return None
    return {
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "username": profile.username,
        "bio": profile.bio,
        "synced_at": profile.synced_at,
    }


def _record_lifecycle_event(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    event_type: str,
    actor_user_id: str | None,
    request_id: str | None,
    payload: dict[str, Any],
) -> None:
    session.add(
        AccountLifecycleEvent(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            request_id=request_id,
            payload_json=redact_metadata(payload),
            created_at=utc_now(),
        )
    )


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(json.dumps(payload, default=str))
    return result
