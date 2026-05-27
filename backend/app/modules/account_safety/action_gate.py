from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Account
from app.services.account_risk import build_account_readiness_risk
from app.services.accounts import get_account
from app.services.sensitive_audit import record_sensitive_audit_event

ACTION_TYPES = (
    "profile.update",
    "profile.photo_upload",
    "story.create",
    "music.add",
    "account.auth",
    "account.import",
    "account.delete",
    "account.export",
    "asset.upload",
    "job.enqueue",
)
OVERRIDE_ALLOWED_CRITICAL_ACTIONS = {"account.auth", "account.delete", "account.export"}


def evaluate_action_gate(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    action_type: str,
    actor_user_id: str | None = None,
    override_reason: str | None = None,
    audit: bool = True,
) -> dict[str, Any]:
    if action_type not in ACTION_TYPES:
        raise ValueError("unsupported action type")
    account = get_account(session, account_id, workspace_id=workspace_id)
    if account is None:
        raise ValueError("account not found")
    risk = build_account_readiness_risk(session, account)
    decision = _decision_for(
        account, action_type=action_type, risk=risk, override_reason=override_reason
    )
    if override_reason and len(override_reason.strip()) < 10:
        raise ValueError("override reason too short")
    if override_reason and audit:
        record_sensitive_audit_event(
            session,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action="job.enqueue.override_used"
            if action_type == "job.enqueue"
            else "account.risk.override_requested",
            entity_type="account",
            entity_id=account_id,
            account_id=account_id,
            override_reason=override_reason,
            risk_level=risk["level"],
            risk_score=risk["score"],
            metadata={"action_type": action_type, "allowed": decision["allowed"]},
        )
    if not decision["allowed"] and audit:
        record_sensitive_audit_event(
            session,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action="job.enqueue.blocked_by_risk"
            if action_type == "job.enqueue"
            else f"{action_type}.blocked_by_risk",
            entity_type="account",
            entity_id=account_id,
            account_id=account_id,
            risk_level=risk["level"],
            risk_score=risk["score"],
            metadata={
                "action_type": action_type,
                "reason_codes": [reason["code"] for reason in risk["reasons"]],
            },
        )
    return decision


def _decision_for(
    account: Account,
    *,
    action_type: str,
    risk: dict[str, Any],
    override_reason: str | None,
) -> dict[str, Any]:
    level = risk["level"]
    requires_override = level == "high" or (
        level == "critical" and action_type in OVERRIDE_ALLOWED_CRITICAL_ACTIONS
    )
    blocked = level == "critical" and action_type not in OVERRIDE_ALLOWED_CRITICAL_ACTIONS
    allowed = not blocked and (level in {"low", "medium"} or bool(override_reason))
    if action_type == "account.delete":
        allowed = not blocked
    return {
        "account_id": account.id,
        "action_type": action_type,
        "allowed": allowed,
        "requires_override": requires_override,
        "blocked": blocked
        or (requires_override and not override_reason and action_type != "account.delete"),
        "risk_level": level,
        "risk_score": risk["score"],
        "reasons": risk["reasons"],
        "required_override_reason": requires_override and action_type != "account.delete",
    }
