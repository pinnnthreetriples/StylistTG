from __future__ import annotations

from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountAuthAttempt,
    AccountBehaviorProfile,
    AccountDeletionRequest,
    AccountExportRequest,
    AccountGgrScore,
    AccountLifecycleEvent,
    AccountOperationLog,
    AccountQuarantine,
    AccountSafetyOverride,
    AccountStatusObservation,
    AccountSurvivalMetric,
    Asset,
    BoughtOnboardingState,
    CrossModuleLoadBucket,
    NeuroCommentAttempt,
    NeuroCommentEvent,
    NeuroCommentGeneratedComment,
    WarmupPreProductionSession,
    WarmupSession,
    new_id,
    utc_now,
)
from app.modules.account_shared.interfaces import lookup_account
from app.services.secret_redaction import redact_metadata


def account_or_raise(session: Session, account_id: str, workspace_id: str) -> Account:
    account = lookup_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    return account


def account_assets(session: Session, account: Account) -> list[Asset]:
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


def active_deletion_request(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    active_statuses: set[str],
) -> AccountDeletionRequest | None:
    return (
        session.execute(
            select(AccountDeletionRequest)
            .where(AccountDeletionRequest.workspace_id == workspace_id)
            .where(AccountDeletionRequest.account_id == account_id)
            .where(AccountDeletionRequest.status.in_(active_statuses))
            .limit(1)
        )
        .scalars()
        .first()
    )


def list_deletion_requests_for_account(
    session: Session, *, account_id: str, workspace_id: str
) -> list[AccountDeletionRequest]:
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


def get_deletion_request_for_account(
    session: Session, *, account_id: str, request_id: str, workspace_id: str
) -> AccountDeletionRequest | None:
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


def list_export_requests_for_account(
    session: Session, *, account_id: str, workspace_id: str
) -> list[AccountExportRequest]:
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


def get_export_request_for_account(
    session: Session, *, account_id: str, request_id: str, workspace_id: str
) -> AccountExportRequest | None:
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


def add_lifecycle_event(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    event_type: str,
    actor_user_id: str | None,
    request_id: str | None,
    payload: dict[str, Any],
    from_state: str | None = None,
    to_state: str | None = None,
    reason: str | None = None,
    occurred_at: Any | None = None,
) -> None:
    session.add(
        AccountLifecycleEvent(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            request_id=request_id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            payload_json=redact_metadata(payload),
            occurred_at=occurred_at,
            created_at=occurred_at or utc_now(),
        )
    )


def list_transition_events_for_account(
    session: Session, *, account_id: str, workspace_id: str, limit: int = 50
) -> list[AccountLifecycleEvent]:
    return list(
        session.execute(
            select(AccountLifecycleEvent)
            .where(AccountLifecycleEvent.workspace_id == workspace_id)
            .where(AccountLifecycleEvent.account_id == account_id)
            .where(AccountLifecycleEvent.event_type == "account.lifecycle.transition")
            .order_by(AccountLifecycleEvent.created_at.desc(), AccountLifecycleEvent.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


# Tables whose rows must be deleted when the parent account is removed.
# Mirror of migration 20260525_0054_account_safety_cascade. DB-level ON DELETE
# CASCADE handles this on Postgres; explicit deletes keep SQLite tests portable.
_CASCADE_MODELS: tuple[tuple[str, Any], ...] = (
    ("account_quarantines", AccountQuarantine),
    ("account_status_observations", AccountStatusObservation),
    ("cross_module_load_buckets", CrossModuleLoadBucket),
    ("account_ggr_scores", AccountGgrScore),
    ("account_behavior_profile", AccountBehaviorProfile),
    ("bought_onboarding_state", BoughtOnboardingState),
    ("account_safety_override", AccountSafetyOverride),
    ("account_lifecycle_event", AccountLifecycleEvent),
    ("account_operation_log", AccountOperationLog),
    ("account_survival_metric", AccountSurvivalMetric),
    ("account_auth_attempt", AccountAuthAttempt),
    ("warmup_pre_production_session", WarmupPreProductionSession),
    ("warmup_session", WarmupSession),
)

# Tables whose account_id is nulled instead of deleted (audit/compliance).
_SET_NULL_MODELS: tuple[tuple[str, Any], ...] = (
    ("neuro_comment_attempts", NeuroCommentAttempt),
    ("neuro_comment_events", NeuroCommentEvent),
    ("neuro_comment_generated_comments", NeuroCommentGeneratedComment),
)


def apply_account_hard_delete_cascade(
    session: Session, *, account: Account
) -> tuple[dict[str, int], dict[str, int]]:
    cascade_counts: dict[str, int] = {}
    for table_name, model in _CASCADE_MODELS:
        result = session.execute(delete(model).where(model.account_id == account.id))
        cursor = cast("CursorResult[Any]", result)
        cascade_counts[table_name] = int(cursor.rowcount or 0)

    set_null_counts: dict[str, int] = {}
    for table_name, model in _SET_NULL_MODELS:
        result = session.execute(
            update(model).where(model.account_id == account.id).values(account_id=None)
        )
        cursor = cast("CursorResult[Any]", result)
        set_null_counts[table_name] = int(cursor.rowcount or 0)

    return cascade_counts, set_null_counts


def delete_account(session: Session, *, account: Account) -> None:
    session.delete(account)


def delete_neuro_comment_events_before(session: Session, *, cutoff: Any) -> int:
    return _delete_older_than(session, NeuroCommentEvent, NeuroCommentEvent.created_at, cutoff)


def delete_status_observations_before(session: Session, *, cutoff: Any) -> int:
    return _delete_older_than(
        session, AccountStatusObservation, AccountStatusObservation.observed_at, cutoff
    )


def delete_load_buckets_before(session: Session, *, cutoff: Any) -> int:
    return _delete_older_than(
        session, CrossModuleLoadBucket, CrossModuleLoadBucket.bucket_start, cutoff
    )


def archive_released_quarantines_before(session: Session, *, cutoff: Any) -> int:
    statement = delete(AccountQuarantine).where(
        AccountQuarantine.released_at < cutoff,
        AccountQuarantine.released_at.is_not(None),
    )
    result = cast(CursorResult[Any], session.execute(statement))
    return int(result.rowcount or 0)


def _delete_older_than(session: Session, model: type[Any], column: Any, cutoff: Any) -> int:
    result = cast(CursorResult[Any], session.execute(delete(model).where(column < cutoff)))
    return int(result.rowcount or 0)


__all__ = [
    "account_assets",
    "account_or_raise",
    "active_deletion_request",
    "add_lifecycle_event",
    "apply_account_hard_delete_cascade",
    "archive_released_quarantines_before",
    "delete_account",
    "delete_load_buckets_before",
    "delete_neuro_comment_events_before",
    "delete_status_observations_before",
    "get_deletion_request_for_account",
    "get_export_request_for_account",
    "list_deletion_requests_for_account",
    "list_export_requests_for_account",
    "list_transition_events_for_account",
]
