from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    DEFAULT_LOCAL_USER_ID,
    Account,
    AccountQuarantine,
    BoughtOnboardingState,
    new_id,
    utc_now,
)
from app.modules.account_ggr.interfaces import calculate_ggr
from app.modules.account_safety.quarantine import create_quarantine, release_quarantine
from app.modules.bought_onboarding.contracts import BoughtOnboardingStatusRead
from app.services.scheduler import schedule_bought_onboarding_action

REST_PERIOD_HOURS = 120
WEAK_GGR_EXTENSION_HOURS = 72

_STEP_COMPLETION = {
    "enable_2fa": 25,
    "terminate_other_sessions": 50,
    "rest_period": 75,
    "ggr_precheck": 90,
    "completed": 100,
}


class BoughtOnboardingNotFound(LookupError):
    pass


def get_onboarding_state(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> BoughtOnboardingState | None:
    return session.execute(
        select(BoughtOnboardingState)
        .where(BoughtOnboardingState.workspace_id == workspace_id)
        .where(BoughtOnboardingState.account_id == account_id)
    ).scalar_one_or_none()


def start_bought_onboarding(
    session: Session,
    *,
    account: Account,
    workspace_id: str,
) -> BoughtOnboardingState:
    existing = get_onboarding_state(session, account_id=account.id, workspace_id=workspace_id)
    if existing is not None:
        return existing

    now = utc_now()
    terminate_at = now + timedelta(hours=24)
    ggr_check_at = now + timedelta(hours=REST_PERIOD_HOURS)
    quarantine = create_quarantine(
        session,
        account_id=account.id,
        workspace_id=workspace_id,
        reason="bought_rest_period",
        duration_hours=REST_PERIOD_HOURS,
        metadata={"source": "bought_onboarding", "rest_period_hours": REST_PERIOD_HOURS},
    )
    terminate_scheduled = schedule_bought_onboarding_action(
        "terminate_other_sessions",
        account_id=account.id,
        workspace_id=workspace_id,
        run_at=terminate_at,
    )
    ggr_scheduled = schedule_bought_onboarding_action(
        "ggr_precheck",
        account_id=account.id,
        workspace_id=workspace_id,
        run_at=ggr_check_at,
    )
    state = BoughtOnboardingState(
        id=new_id(),
        workspace_id=workspace_id,
        account_id=account.id,
        current_step="enable_2fa",
        started_at=now,
        details_json={
            "enable_2fa": {"status": "required"},
            "terminate_other_sessions": {
                "status": "scheduled" if terminate_scheduled else "schedule_failed",
                "scheduled_for": terminate_at.isoformat(),
            },
            "rest_period": {
                "status": "active",
                "quarantine_id": quarantine.id,
                "until": quarantine.until.isoformat(),
            },
            "ggr_precheck": {
                "status": "scheduled" if ggr_scheduled else "schedule_failed",
                "scheduled_for": ggr_check_at.isoformat(),
            },
        },
    )
    session.add(state)
    session.flush()
    return state


def process_rest_period_ggr_check(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> BoughtOnboardingState:
    state = get_onboarding_state(session, account_id=account_id, workspace_id=workspace_id)
    account = _account_for_workspace(session, account_id=account_id, workspace_id=workspace_id)
    if state is None or account is None:
        raise BoughtOnboardingNotFound(account_id)

    bucket = _calculate_ggr_bucket(session, account, workspace_id)
    quarantine = _latest_rest_quarantine(
        session,
        account_id=account_id,
        workspace_id=workspace_id,
    )
    details = dict(state.details_json or {})
    details["ggr_bucket"] = bucket
    details["ggr_checked_at"] = utc_now().isoformat()

    if bucket == "weak":
        if quarantine is not None:
            quarantine.until = utc_now() + timedelta(hours=WEAK_GGR_EXTENSION_HOURS)
            metadata = dict(quarantine.metadata_json or {})
            metadata["ggr_bucket"] = bucket
            metadata["extended_hours"] = WEAK_GGR_EXTENSION_HOURS
            quarantine.metadata_json = metadata
        state.current_step = "ggr_precheck"
        details["ggr_precheck"] = {"status": "weak_extended"}
    else:
        if quarantine is not None and quarantine.released_at is None:
            release_quarantine(
                session,
                quarantine_id=quarantine.id,
                workspace_id=workspace_id,
                released_by=DEFAULT_LOCAL_USER_ID,
                reason="bought_onboarding_ggr_passed",
            )
        state.current_step = "completed"
        state.completed_at = utc_now()
        details["ggr_precheck"] = {"status": "passed"}

    state.details_json = details
    session.flush()
    return state


def terminate_other_sessions(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    tdlib_client: Any | None = None,
) -> BoughtOnboardingState:
    state = get_onboarding_state(session, account_id=account_id, workspace_id=workspace_id)
    if state is None:
        raise BoughtOnboardingNotFound(account_id)
    details = dict(state.details_json or {})
    enable_details = dict(details.get("enable_2fa") or {})
    if enable_details.get("status") != "completed":
        raise ValueError("2FA must be enabled before terminating other sessions")
    if tdlib_client is not None:
        tdlib_client.send_query({"@type": "terminateAllOtherSessions"})
    details["terminate_other_sessions"] = {
        **dict(details.get("terminate_other_sessions") or {}),
        "status": "completed",
        "completed_at": utc_now().isoformat(),
    }
    state.current_step = "rest_period"
    state.details_json = details
    session.flush()
    return state


def enable_two_factor(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    new_password: str,
    hint: str | None = None,
    tdlib_client: Any | None = None,
) -> BoughtOnboardingState:
    state = get_onboarding_state(session, account_id=account_id, workspace_id=workspace_id)
    if state is None:
        raise BoughtOnboardingNotFound(account_id)
    if tdlib_client is not None:
        tdlib_client.send_query(
            {
                "@type": "setPassword",
                "old_password": "",
                "new_password": new_password,
                "new_hint": hint or "",
                "set_recovery_email_address": False,
                "new_recovery_email_address": "",
            }
        )
    details = dict(state.details_json or {})
    details["enable_2fa"] = {"status": "completed", "completed_at": utc_now().isoformat()}
    state.current_step = "terminate_other_sessions"
    state.details_json = details
    session.flush()
    return state


def status_read(state: BoughtOnboardingState) -> BoughtOnboardingStatusRead:
    return BoughtOnboardingStatusRead(
        account_id=state.account_id,
        current_step=state.current_step,  # type: ignore[arg-type]
        completion_percent=_STEP_COMPLETION.get(state.current_step, 0),
        started_at=state.started_at,
        completed_at=state.completed_at,
        details_json=state.details_json or {},
    )


def run_terminate_other_sessions(account_id: str, workspace_id: str) -> None:
    from app.db import SessionLocal

    with SessionLocal() as session:
        terminate_other_sessions(session, account_id=account_id, workspace_id=workspace_id)
        session.commit()


def run_rest_period_ggr_check(account_id: str, workspace_id: str) -> None:
    from app.db import SessionLocal

    with SessionLocal() as session:
        process_rest_period_ggr_check(session, account_id=account_id, workspace_id=workspace_id)
        session.commit()


def _account_for_workspace(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> Account | None:
    return session.execute(
        select(Account).where(Account.id == account_id).where(Account.workspace_id == workspace_id)
    ).scalar_one_or_none()


def _latest_rest_quarantine(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
) -> AccountQuarantine | None:
    return session.execute(
        select(AccountQuarantine)
        .where(AccountQuarantine.workspace_id == workspace_id)
        .where(AccountQuarantine.account_id == account_id)
        .where(AccountQuarantine.reason == "bought_rest_period")
        .where(AccountQuarantine.released_at.is_(None))
        .order_by(AccountQuarantine.until.desc())
        .limit(1)
    ).scalar_one_or_none()


def _calculate_ggr_bucket(session: Session, account: Account, workspace_id: str) -> str:
    return calculate_ggr(session, account, workspace_id, force=True).bucket


__all__ = [
    "BoughtOnboardingNotFound",
    "REST_PERIOD_HOURS",
    "WEAK_GGR_EXTENSION_HOURS",
    "enable_two_factor",
    "get_onboarding_state",
    "process_rest_period_ggr_check",
    "run_rest_period_ggr_check",
    "run_terminate_other_sessions",
    "start_bought_onboarding",
    "status_read",
    "terminate_other_sessions",
]
