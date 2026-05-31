from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.contracts.neuro_commenting import (
    NeuroLiveReadinessCheckRead,
    NeuroLiveReadinessRead,
)
from app.models import Account, NeuroCommentGeneratedComment
from app.modules.account_safety.interfaces import evaluate as evaluate_safety_gate
from app.modules.neuro_commenting import repository
from app.modules.neuro_commenting.account_selector import AccountSelector
from app.modules.neuro_commenting.channel_rules_service import ChannelRulesService
from app.modules.neuro_commenting.enums import (
    NeuroCampaignAccountStatus,
    NeuroCampaignStatus,
    NeuroGeneratedApprovalStatus,
    NeuroTargetStatus,
)


Severity = Literal["info", "warning", "blocker"]


def _empty_details() -> dict[str, Any]:
    return {}


@dataclass(frozen=True)
class _Check:
    code: str
    severity: Severity
    message: str
    details: dict[str, Any] = field(default_factory=_empty_details)


class LiveReadinessService:
    def __init__(
        self,
        *,
        config: Settings = settings,
        limiter_ready: bool | None = None,
    ) -> None:
        self._config = config
        self._limiter_ready = limiter_ready

    def check(
        self, session: Session, *, campaign_id: str, workspace_id: str
    ) -> NeuroLiveReadinessRead:
        campaign = repository.require_campaign(
            session, campaign_id=campaign_id, workspace_id=workspace_id
        )
        checks: list[_Check] = []
        _append_campaign_checks(checks, campaign)
        accounts = repository.list_campaign_accounts(session, campaign_id=campaign.id)
        active_accounts = _append_active_account_checks(session, checks, campaign, accounts)
        _append_account_safety_checks(
            session, checks, active_accounts=active_accounts, workspace_id=workspace_id
        )
        _append_target_checks(session, checks, campaign_id=campaign.id, workspace_id=workspace_id)
        _append_approval_checks(session, checks, campaign_id=campaign.id)
        self._append_send_dependency_checks(checks)
        return _readiness_response(campaign.id, checks)

    def _append_send_dependency_checks(self, checks: list[_Check]) -> None:
        _append(
            checks,
            bool(self._config.neuro_comment_tdlib_send_enabled),
            "TDLIB_SEND_ENABLED",
            "NEURO_COMMENT_SEND_DISABLED",
            "TDLib neuro-comment sending flag is enabled",
            "TDLib neuro-comment sending flag must be enabled",
        )
        limiter_ready = (
            self._limiter_ready
            if self._limiter_ready is not None
            else not getattr(self._config, "neuro_comment_require_redis_limiter_for_send", True)
        )
        _append(
            checks,
            bool(limiter_ready),
            "REDIS_LIMITER_READY",
            "NEURO_COMMENT_RATE_LIMITER_NOT_READY",
            "Redis limiter is ready",
            "Redis limiter is required before live send",
        )


def _append_campaign_checks(checks: list[_Check], campaign: Any) -> None:
    _append(
        checks,
        campaign.status == NeuroCampaignStatus.RUNNING.value,
            "CAMPAIGN_RUNNING",
            "CAMPAIGN_NOT_RUNNING",
            "campaign is running",
            "campaign must be running",
    )
    _append(
        checks,
        not campaign.dry_run,
        "CAMPAIGN_LIVE_MODE",
        "CAMPAIGN_DRY_RUN",
        "campaign dry-run is disabled",
        "campaign dry-run must be disabled",
    )
    _append(
        checks,
        campaign.send_mode == "manual_approval",
        "SEND_MODE_MANUAL_APPROVAL",
        "SEND_MODE_NOT_MANUAL_APPROVAL",
        "send mode is manual approval",
        "send mode must be manual_approval",
    )
    _append(
        checks,
        not campaign.auto_send_enabled,
        "AUTO_SEND_DISABLED",
        "AUTO_SEND_ENABLED",
        "auto-send is disabled",
        "auto-send must remain disabled",
    )


def _append_active_account_checks(
    session: Session, checks: list[_Check], campaign: Any, accounts: list[Any]
) -> list[Any]:
    active_accounts = [
        account for account in accounts if account.status == NeuroCampaignAccountStatus.ACTIVE.value
    ]
    if not active_accounts:
        checks.append(_Check("NO_ACTIVE_ACCOUNT", "blocker", "at least one active account is required"))
        return active_accounts
    checks.append(_Check("ACTIVE_ACCOUNT_AVAILABLE", "info", "active account is available"))
    selection = AccountSelector(session=session).select_account(campaign, accounts, None)
    selected = selection.account
    if selected is None:
        checks.append(
            _Check(
                "ACCOUNT_RUNTIME_NOT_READY",
                "blocker",
                "selected account must be execution_usable with ready runtime and session",
            )
        )
        return active_accounts
    _append_selected_account_runtime_check(session, checks, selected.account_id)
    return active_accounts


def _append_selected_account_runtime_check(
    session: Session, checks: list[_Check], account_id: str
) -> None:
    account = session.get(Account, account_id)
    runtime = account.runtime_state if account is not None else None
    account_ready = bool(
        account is not None
        and account.account_state == "execution_usable"
        and runtime is not None
        and runtime.runtime_health == "ready"
        and runtime.session_present
    )
    _append(
        checks,
        account_ready,
        "ACCOUNT_RUNTIME_READY",
        "ACCOUNT_RUNTIME_NOT_READY",
        "selected account runtime is ready",
        "selected account must be execution_usable with ready runtime and session",
    )


def _append_account_safety_checks(
    session: Session,
    checks: list[_Check],
    *,
    active_accounts: list[Any],
    workspace_id: str,
) -> None:
    for campaign_account in active_accounts:
        _append_account_safety_gate_check(
            session,
            checks,
            workspace_id=workspace_id,
            account_id=campaign_account.account_id,
        )


def _append_target_checks(
    session: Session, checks: list[_Check], *, campaign_id: str, workspace_id: str
) -> None:
    targets, _total = repository.list_targets(session, campaign_id=campaign_id, page=1, limit=100)
    active_targets = [target for target in targets if target.status == NeuroTargetStatus.ACTIVE.value]
    if not active_targets:
        checks.append(_Check("NO_ACTIVE_TARGET", "blocker", "at least one active target is required"))
        return
    checks.append(_Check("ACTIVE_TARGET_AVAILABLE", "info", "active target is available"))
    for target in active_targets:
        _append_target_rule_checks(session, checks, target=target, workspace_id=workspace_id)


def _append_target_rule_checks(
    session: Session, checks: list[_Check], *, target: Any, workspace_id: str
) -> None:
    if not target.discussion_chat_id:
        checks.append(_Check("TARGET_NO_DISCUSSION", "blocker", "active target has no discussion chat"))
    rule_status = ChannelRulesService().target_rule_status(
        session, workspace_id=workspace_id, target_ref=target.channel_ref
    )
    if rule_status == "blacklist":
        checks.append(
            _Check("CHANNEL_RULE_BLOCKED", "blocker", "selected target is blocked by channel rules")
        )
    elif rule_status == "whitelist":
        checks.append(
            _Check("CHANNEL_RULE_ALLOWED", "info", "selected target is explicitly whitelisted")
        )


def _append_approval_checks(session: Session, checks: list[_Check], *, campaign_id: str) -> None:
    unresolved_count = _approved_unresolved_count(session, campaign_id=campaign_id)
    if unresolved_count:
        checks.append(
            _Check(
                "DISCUSSION_MESSAGE_NOT_RESOLVED",
                "blocker",
                "approved comments require resolved discussion messages before send",
            )
        )
    else:
        checks.append(_Check("DISCUSSION_MAPPING_READY", "info", "approved comments have discussion mapping"))


def _readiness_response(campaign_id: str, checks: list[_Check]) -> NeuroLiveReadinessRead:
    read_checks = [
        NeuroLiveReadinessCheckRead(
            code=check.code,
            severity=check.severity,
            message=check.message,
            details=check.details,
        )
        for check in checks
    ]
    ready = not any(check.severity == "blocker" for check in read_checks)
    return NeuroLiveReadinessRead(campaign_id=campaign_id, ready=ready, checks=read_checks)


def _append(
    checks: list[_Check],
    condition: bool,
    ok_code: str,
    blocker_code: str,
    ok_message: str,
    blocker_message: str,
) -> None:
    checks.append(
        _Check(
            ok_code if condition else blocker_code,
            "info" if condition else "blocker",
            ok_message if condition else blocker_message,
        )
    )


def _approved_unresolved_count(session: Session, *, campaign_id: str) -> int:
    count = 0
    comments = (
        session.query(NeuroCommentGeneratedComment)
        .filter(
            NeuroCommentGeneratedComment.campaign_id == campaign_id,
            NeuroCommentGeneratedComment.approval_status
            == NeuroGeneratedApprovalStatus.APPROVED.value,
        )
        .all()
    )
    for comment in comments:
        if comment.observed_post_id is None:
            count += 1
            continue
        observed = repository.get_observed_post(
            session, observed_post_id=comment.observed_post_id, campaign_id=campaign_id
        )
        if observed is None or not observed.discussion_message_id:
            count += 1
    return count


def _append_account_safety_gate_check(
    session: Session,
    checks: list[_Check],
    *,
    workspace_id: str,
    account_id: str,
) -> None:
    verdict = evaluate_safety_gate(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        intent="commenting",
    )
    if verdict.severity == "ok":
        return
    reasons = [reason.model_dump(mode="json") for reason in verdict.reasons]
    details = {"referenced_account_id": account_id, "reasons": reasons}
    if verdict.severity == "blocked":
        checks.append(
            _Check(
                "account_safety_blocked",
                "blocker",
                "campaign account is blocked by account safety gate",
                details,
            )
        )
        return
    checks.append(
        _Check(
            "account_safety_warning",
            "warning",
            "campaign account has account safety gate warnings",
            details,
        )
    )
