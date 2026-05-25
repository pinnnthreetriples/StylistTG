from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.tdlib_auth import search_chat_messages
from app.config import Settings, settings
from app.logging_utils import log_event, log_warn
from app.models import (
    Account,
    NeuroAttemptStatus,
    NeuroCommentAttempt,
    NeuroCommentCampaign,
    NeuroCommentObservedPost,
    NeuroCommentTarget,
)
from app.observability.safety_metrics import safety_metrics
from app.services.idempotency_keys import derive_random_id
from app.services.neuro_commenting.tdlib_runtime import NeuroTdlibRuntime


def _empty_account_errors() -> dict[str, int]:
    return {}


@dataclass
class ReconcileReport:
    scanned: int = 0
    resolved_sent: int = 0
    resolved_failed: int = 0
    skipped_no_idem_key: int = 0
    per_account_errors: dict[str, int] = field(default_factory=_empty_account_errors)


class TdlibSearchClient(Protocol):
    def search_chat_messages(
        self,
        *,
        account_id: str,
        chat_id: int,
        random_id: int | None = None,
        limit: int = 10,
    ) -> list[Any]: ...


class RuntimeTdlibSearchClient:
    def __init__(self, *, config: Settings = settings) -> None:
        self._config = config
        self._runtime = NeuroTdlibRuntime(config=config)

    def search_chat_messages(
        self,
        *,
        account_id: str,
        chat_id: int,
        random_id: int | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        with self._runtime.ready_client_context(account_id) as client:
            return search_chat_messages(
                client,
                chat_id=chat_id,
                random_id=random_id,
                limit=limit,
                timeout_seconds=self._config.tdlib_receive_timeout_seconds,
            )


def run_reconcile_tick(
    session: Session,
    tdlib_client: TdlibSearchClient,
    *,
    now: datetime,
    stuck_threshold_seconds: int = 300,
    max_attempts_per_tick: int = 100,
) -> ReconcileReport:
    cutoff = now - timedelta(seconds=stuck_threshold_seconds)
    statement = (
        select(NeuroCommentAttempt)
        .where(
            NeuroCommentAttempt.status.in_(
                [NeuroAttemptStatus.SENDING.value, NeuroAttemptStatus.RESERVED.value]
            ),
            NeuroCommentAttempt.updated_at < cutoff,
        )
        .limit(max_attempts_per_tick)
        .with_for_update(skip_locked=True)
    )
    attempts = list(session.execute(statement).scalars().all())
    report = ReconcileReport(scanned=len(attempts))

    for attempt in attempts:
        context = _load_context(session, attempt)
        workspace_id = context.workspace_id
        if context.tenant_violation:
            _mark_tenant_violation(attempt, now)
            report.resolved_failed += 1
            safety_metrics.attempts_stuck(workspace_id=workspace_id, resolution="failed")
            log_event(
                "reconcile_workspace_mismatch",
                workspace_id=workspace_id,
                attempt_id=attempt.id,
                account_id=attempt.account_id,
                reason=context.tenant_violation,
            )
            continue
        if not attempt.idempotency_key:
            report.skipped_no_idem_key += 1
            safety_metrics.attempts_stuck(workspace_id=workspace_id, resolution="skipped")
            log_event(
                "attempt_reconcile_skipped_no_idempotency_key",
                workspace_id=workspace_id,
                attempt_id=attempt.id,
                account_id=attempt.account_id,
            )
            continue

        account_id = attempt.account_id
        chat_id = _discussion_chat_id(context)
        if account_id is None or chat_id is None:
            _mark_lost(attempt, now)
            report.resolved_failed += 1
            safety_metrics.attempts_stuck(workspace_id=workspace_id, resolution="failed")
            log_event(
                "attempt_reconciled_failed",
                workspace_id=workspace_id,
                attempt_id=attempt.id,
                account_id=account_id,
                reason="missing_account_or_discussion_chat",
            )
            continue

        random_id = derive_random_id(attempt.idempotency_key)
        try:
            results = tdlib_client.search_chat_messages(
                account_id=account_id,
                chat_id=chat_id,
                random_id=random_id,
                limit=1,
            )
        except Exception as exc:
            report.per_account_errors[account_id] = report.per_account_errors.get(account_id, 0) + 1
            log_warn(
                "attempt_reconcile_tdlib_error",
                workspace_id=workspace_id,
                attempt_id=attempt.id,
                account_id=account_id,
                error_class=exc.__class__.__name__,
                error=str(exc),
            )
            continue

        if results:
            message_id = _message_id(results[0])
            attempt.status = NeuroAttemptStatus.SENT.value
            attempt.telegram_message_id = message_id
            attempt.external_message_id_provisional = None
            attempt.sent_at = now
            attempt.error_code = None
            attempt.error_message = None
            report.resolved_sent += 1
            safety_metrics.attempts_stuck(workspace_id=workspace_id, resolution="sent")
            log_event(
                "attempt_reconciled_sent",
                workspace_id=workspace_id,
                attempt_id=attempt.id,
                account_id=account_id,
                telegram_message_id=message_id,
            )
        else:
            _mark_lost(attempt, now)
            report.resolved_failed += 1
            safety_metrics.attempts_stuck(workspace_id=workspace_id, resolution="failed")
            log_event(
                "attempt_reconciled_failed",
                workspace_id=workspace_id,
                attempt_id=attempt.id,
                account_id=account_id,
                reason="not_found",
            )

    return report


@dataclass(frozen=True)
class _AttemptContext:
    workspace_id: str | None
    observed_discussion_chat_id: str | None
    target_discussion_chat_id: str | None
    tenant_violation: str | None = None


def _load_context(session: Session, attempt: NeuroCommentAttempt) -> _AttemptContext:
    campaign = session.scalar(
        select(NeuroCommentCampaign).where(NeuroCommentCampaign.id == attempt.campaign_id)
    )
    if campaign is None:
        return _AttemptContext(None, None, None, "campaign_missing")

    if attempt.account_id is not None:
        account = session.scalar(
            select(Account)
            .where(Account.id == attempt.account_id)
            .where(Account.workspace_id == campaign.workspace_id)
        )
        if account is None:
            return _AttemptContext(campaign.workspace_id, None, None, "account_workspace_mismatch")

    observed = (
        session.scalar(
            select(NeuroCommentObservedPost)
            .where(NeuroCommentObservedPost.id == attempt.observed_post_id)
            .where(NeuroCommentObservedPost.campaign_id == campaign.id)
        )
        if attempt.observed_post_id is not None
        else None
    )
    if attempt.observed_post_id is not None and observed is None:
        return _AttemptContext(
            campaign.workspace_id, None, None, "observed_post_workspace_mismatch"
        )

    target = (
        session.scalar(
            select(NeuroCommentTarget)
            .where(NeuroCommentTarget.id == attempt.target_id)
            .where(NeuroCommentTarget.campaign_id == campaign.id)
        )
        if attempt.target_id is not None
        else None
    )
    if attempt.target_id is not None and target is None:
        return _AttemptContext(campaign.workspace_id, None, None, "target_workspace_mismatch")

    return _AttemptContext(
        workspace_id=campaign.workspace_id,
        observed_discussion_chat_id=observed.discussion_chat_id if observed is not None else None,
        target_discussion_chat_id=target.discussion_chat_id if target is not None else None,
    )


def _discussion_chat_id(context: _AttemptContext) -> int | None:
    value = context.observed_discussion_chat_id or context.target_discussion_chat_id
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _message_id(message: Any) -> str:
    if isinstance(message, dict):
        message_dict = cast(dict[str, Any], message)
        return str(message_dict.get("id") or "")
    return str(getattr(message, "id", ""))


def _mark_lost(attempt: NeuroCommentAttempt, now: datetime) -> None:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    attempt.status = NeuroAttemptStatus.FAILED.value
    attempt.error_code = "stuck_attempt_lost"
    attempt.error_message = None
    attempt.external_message_id_provisional = None
    attempt.failed_at = now


def _mark_tenant_violation(attempt: NeuroCommentAttempt, now: datetime) -> None:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    attempt.status = NeuroAttemptStatus.FAILED.value
    attempt.error_code = "tenant_invariant_violation"
    attempt.error_message = None
    attempt.external_message_id_provisional = None
    attempt.failed_at = now


__all__ = [
    "ReconcileReport",
    "RuntimeTdlibSearchClient",
    "TdlibSearchClient",
    "run_reconcile_tick",
]
