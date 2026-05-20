from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
from typing import Literal, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountState,
    AccountStatusObservation,
    NeuroCommentCampaign,
    NeuroCommentCampaignAccount,
    NeuroCommentEvent,
    WarmupSession,
    WarmupStatus,
    new_id,
    utc_now,
)
from app.modules.warmup.events import write_warmup_event
from app.services.account_quarantine import AccountQuarantineService, get_active_quarantine

AutoAction = Literal["paused", "quarantine", "cooldown", "none"]

IP_CHANGE_COOLDOWN_MINUTES = 30
STICKY_IP_MAX_DISTINCT_HASHES = 3
CONSECUTIVE_FAILURE_THRESHOLD = 3  # TODO: move into WorkspaceSafetyPolicy.

_AUTHORIZED_STATES = {AccountState.AUTHORIZED_READY.value, AccountState.EXECUTION_USABLE.value}
_HEALTHY_PROXY_STATUSES = {"ok", "tcp_working", "tdlib_working"}
_AUTO_PAUSE_WARMUP_STATUSES = [
    WarmupStatus.VALIDATING.value,
    WarmupStatus.SCHEDULED.value,
    WarmupStatus.ACTIVE.value,
]


@dataclass(frozen=True)
class AccountStatusProbeResult:
    proxy_healthy: bool
    proxy_host: str | None
    tdlib_authorized: bool
    device_model: str | None


class AccountStatusProbe(Protocol):
    def check(self, account: Account) -> AccountStatusProbeResult: ...


class DatabaseSnapshotStatusProbe:
    """Safe default probe: uses persisted runtime/proxy state, not live TDLib calls."""

    def check(self, account: Account) -> AccountStatusProbeResult:
        proxy = account.proxy
        runtime = account.runtime_state
        return AccountStatusProbeResult(
            proxy_healthy=bool(proxy and proxy.status in _HEALTHY_PROXY_STATUSES),
            proxy_host=proxy.host if proxy is not None else None,
            tdlib_authorized=bool(
                runtime
                and runtime.session_present
                and not runtime.reauth_required
                and account.account_state in _AUTHORIZED_STATES
            ),
            device_model=None,
        )


class AccountStatusMonitor:
    def __init__(self, *, probe: AccountStatusProbe | None = None) -> None:
        self._probe = probe or DatabaseSnapshotStatusProbe()

    @staticmethod
    def hash_proxy_host(host: str | None) -> str | None:
        if not host:
            return None
        return hashlib.sha256(host.strip().lower().encode("utf-8")).hexdigest()

    @staticmethod
    def hash_device_model(device_model: str | None) -> str | None:
        if not device_model:
            return None
        return hashlib.sha256(device_model.strip().lower().encode("utf-8")).hexdigest()

    def tick(
        self,
        session: Session,
        *,
        workspace_id: str | None = None,
        now: datetime | None = None,
    ) -> list[AccountStatusObservation]:
        query = select(Account).where(Account.account_state != AccountState.DISABLED.value)
        if workspace_id is not None:
            query = query.where(Account.workspace_id == workspace_id)
        observations: list[AccountStatusObservation] = []
        for account in session.execute(query.order_by(Account.updated_at.asc())).scalars():
            observations.append(
                self.observe_account(
                    session,
                    account_id=account.id,
                    workspace_id=account.workspace_id,
                    now=now,
                    account=account,
                )
            )
        return observations

    def observe_account(
        self,
        session: Session,
        *,
        account_id: str,
        workspace_id: str,
        now: datetime | None = None,
        account: Account | None = None,
    ) -> AccountStatusObservation:
        timestamp = now or utc_now()
        account = account or _get_account(session, account_id=account_id, workspace_id=workspace_id)
        previous = _latest_observation(session, account_id=account_id, workspace_id=workspace_id)
        probe_result = self._probe.check(account)
        proxy_ip_hash = self.hash_proxy_host(probe_result.proxy_host)
        device_model_hash = self.hash_device_model(probe_result.device_model)
        consecutive_failures = _next_consecutive_failures(previous, probe_result)
        details: dict[str, object] = {
            "proxy_host_present": probe_result.proxy_host is not None,
            "threshold": CONSECUTIVE_FAILURE_THRESHOLD,
        }
        auto_action_taken: AutoAction = "none"

        if _changed(previous.proxy_ip_hash if previous else None, proxy_ip_hash):
            auto_action_taken = "cooldown"
            details.update(
                {
                    "reason": "ip_change_detected",
                    "cooldown_minutes": IP_CHANGE_COOLDOWN_MINUTES,
                    "previous_proxy_ip_hash": previous.proxy_ip_hash if previous else None,
                }
            )

        if _changed(previous.device_model_hash if previous else None, device_model_hash):
            details.update(
                {
                    "device_fingerprint_changed": True,
                    "previous_device_model_hash": previous.device_model_hash if previous else None,
                }
            )

        observation = AccountStatusObservation(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            observed_at=timestamp,
            proxy_healthy=probe_result.proxy_healthy,
            proxy_ip_hash=proxy_ip_hash,
            tdlib_authorized=probe_result.tdlib_authorized,
            device_model_hash=device_model_hash,
            consecutive_failures=consecutive_failures,
            auto_action_taken=auto_action_taken,
            details_json=details,
        )
        session.add(observation)
        session.flush()

        if (
            _distinct_proxy_hashes_last_hour(
                session,
                account_id=account_id,
                workspace_id=workspace_id,
                now=timestamp,
            )
            > STICKY_IP_MAX_DISTINCT_HASHES
        ):
            if (
                get_active_quarantine(
                    session, account_id=account_id, workspace_id=workspace_id, now=timestamp
                )
                is None
            ):
                AccountQuarantineService(session).open_quarantine(
                    account_id=account_id,
                    workspace_id=workspace_id,
                    reason="status_degraded",
                    duration_hours=24,
                    metadata={"source": "account_status_monitor", "reason": "sticky_ip_violation"},
                )
            observation.auto_action_taken = "quarantine"
            observation.details_json = {**observation.details_json, "reason": "sticky_ip_violation"}

        if _crossed_failure_threshold(previous, consecutive_failures):
            _auto_pause_account(
                session, account_id=account_id, workspace_id=workspace_id, now=timestamp
            )
            if observation.auto_action_taken == "none":
                observation.auto_action_taken = "paused"
            observation.details_json = {
                **observation.details_json,
                "auto_pause": "consecutive_failures",
            }

        session.flush()
        return observation


def is_in_ip_change_cooldown(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime | None = None,
) -> bool:
    observation = _latest_observation(session, account_id=account_id, workspace_id=workspace_id)
    if observation is None or observation.auto_action_taken != "cooldown":
        return False
    check_time = now or utc_now()
    return observation.observed_at + timedelta(minutes=IP_CHANGE_COOLDOWN_MINUTES) > check_time


def run_account_status_monitor_tick(
    session: Session,
    *,
    workspace_id: str | None = None,
    now: datetime | None = None,
) -> list[AccountStatusObservation]:
    return AccountStatusMonitor().tick(session, workspace_id=workspace_id, now=now)


def _get_account(session: Session, *, account_id: str, workspace_id: str) -> Account:
    account = session.execute(
        select(Account).where(Account.id == account_id).where(Account.workspace_id == workspace_id)
    ).scalar_one_or_none()
    if account is None:
        raise ValueError("account not found")
    return account


def _latest_observation(
    session: Session, *, account_id: str, workspace_id: str
) -> AccountStatusObservation | None:
    return session.execute(
        select(AccountStatusObservation)
        .where(AccountStatusObservation.workspace_id == workspace_id)
        .where(AccountStatusObservation.account_id == account_id)
        .order_by(AccountStatusObservation.observed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _next_consecutive_failures(
    previous: AccountStatusObservation | None,
    probe_result: AccountStatusProbeResult,
) -> int:
    if probe_result.proxy_healthy and probe_result.tdlib_authorized:
        return 0
    return (previous.consecutive_failures if previous is not None else 0) + 1


def _changed(previous_hash: str | None, current_hash: str | None) -> bool:
    return bool(previous_hash and current_hash and previous_hash != current_hash)


def _distinct_proxy_hashes_last_hour(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
) -> int:
    return int(
        session.execute(
            select(func.count(func.distinct(AccountStatusObservation.proxy_ip_hash)))
            .where(AccountStatusObservation.workspace_id == workspace_id)
            .where(AccountStatusObservation.account_id == account_id)
            .where(AccountStatusObservation.observed_at >= now - timedelta(minutes=60))
            .where(AccountStatusObservation.proxy_ip_hash.is_not(None))
        ).scalar_one()
        or 0
    )


def _crossed_failure_threshold(
    previous: AccountStatusObservation | None,
    consecutive_failures: int,
) -> bool:
    previous_failures = previous.consecutive_failures if previous is not None else 0
    return (
        previous_failures < CONSECUTIVE_FAILURE_THRESHOLD
        and consecutive_failures >= CONSECUTIVE_FAILURE_THRESHOLD
    )


def _auto_pause_account(
    session: Session,
    *,
    account_id: str,
    workspace_id: str,
    now: datetime,
) -> None:
    paused_warmups: list[str] = []
    warmups = session.execute(
        select(WarmupSession)
        .where(WarmupSession.workspace_id == workspace_id)
        .where(WarmupSession.account_id == account_id)
        .where(WarmupSession.status.in_(_AUTO_PAUSE_WARMUP_STATUSES))
    ).scalars()
    for warmup_session in warmups:
        warmup_session.status = WarmupStatus.PAUSED_RISK.value
        warmup_session.paused_at = now
        warmup_session.updated_at = now
        warmup_session.next_micro_session_at = None
        warmup_session.next_step_at = None
        write_warmup_event(
            session,
            warmup_session,
            "paused_risk",
            {"reason": "account_status_monitor_consecutive_failures"},
        )
        paused_warmups.append(warmup_session.id)

    paused_campaign_accounts = 0
    campaign_accounts = session.execute(
        select(NeuroCommentCampaignAccount)
        .join(NeuroCommentCampaign)
        .where(NeuroCommentCampaign.workspace_id == workspace_id)
        .where(NeuroCommentCampaignAccount.account_id == account_id)
        .where(NeuroCommentCampaignAccount.status == "active")
    ).scalars()
    for campaign_account in campaign_accounts:
        campaign_account.status = "paused"
        paused_campaign_accounts += 1

    session.add(
        NeuroCommentEvent(
            id=new_id(),
            workspace_id=workspace_id,
            account_id=account_id,
            event_type="account_auto_paused",
            event_level="warning",
            message="Account auto-paused after repeated status monitor failures",
            data_json={
                "source": "account_status_monitor",
                "consecutive_failures": CONSECUTIVE_FAILURE_THRESHOLD,
                "paused_warmup_session_ids": paused_warmups,
                "paused_campaign_accounts": paused_campaign_accounts,
            },
            created_at=now,
        )
    )
