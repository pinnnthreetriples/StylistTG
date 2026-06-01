from __future__ import annotations

# pyright: reportPrivateUsage=false

from datetime import timedelta
from typing import Any
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.modules.account_safety.cache import (
    InMemorySafetyGateCache,
    NullSafetyGateCache,
    RedisSafetyGateCache,
    SafetyGateCache,
)
from app.modules.account_safety.gate_contracts import (
    SafetyGateIntent,
    SafetyGateReason,
    SafetyGateVerdict,
)
from app.modules.account_safety.policy import (
    get_consecutive_failure_threshold,
)
from app.models import (
    AccountState,
    WorkspaceSafetyPolicy,
    utc_now,
)
from app.modules.account_safety.quarantine import get_active_quarantine
from app.services.cross_module_load_tracker import current_load, evaluate_threshold
from app.services.feature_flags import is_safety_pipeline_v2_enabled
from app.observability.safety_metrics import SafetyMetrics, safety_metrics
from app.modules.account_ggr.interfaces import calculate_ggr, get_ggr_score
from app.modules.account_safety.gate_helpers import (
    AccountSafetyGateAccountNotFound,
    _commenting_reasons,
    _warmup_reasons,
    _editing_reasons,
    _policy,
    _effective_safety_mode,
    _cross_module_safety_mode,
    _account,
    _account_cache_state,
    _cache_key,
    _stale_cache_key,
    _default_cache,
    _default_redis,
    _fail_closed_verdict,
    _reason,
    _proxy_reason,
    _terminal_reason,
    _proxy_healthy,
    _latest_warmup,
    _latest_status,
    _is_status_degraded,
    _aggregate_severity,
    _as_utc,
)

_GATE_REEXPORTS = (
    AccountSafetyGateAccountNotFound,
    InMemorySafetyGateCache,
    NullSafetyGateCache,
    RedisSafetyGateCache,
)

CACHE_TTL_SECONDS = 60
STALE_CACHE_TTL_SECONDS = 300
COLD_CALL_BUDGET_PER_MINUTE = 1
_HEALTHY_PROXY_STATUSES = {"ok", "tcp_working", "tdlib_working"}
_TERMINAL_ACCOUNT_STATES = {
    AccountState.DISABLED.value,
    AccountState.MANUAL_INTERVENTION_NEEDED.value,
}
_CRITICAL_ACCOUNT_STATES = {
    *_TERMINAL_ACCOUNT_STATES,
    AccountState.RUNTIME_BROKEN.value,
    AccountState.REAUTH_REQUIRED.value,
}


class AccountSafetyGate:
    def __init__(
        self,
        *,
        cache: SafetyGateCache | None = None,
        redis_client: Any | None = None,
        metrics: SafetyMetrics | None = None,
    ) -> None:
        self._cache = cache if cache is not None else _default_cache()
        self.redis = (
            redis_client
            if redis_client is not None
            else (_default_redis() if cache is None else None)
        )
        self._metrics = metrics or safety_metrics

    def evaluate(
        self,
        session: Session,
        *,
        workspace_id: str,
        account_id: str,
        intent: SafetyGateIntent,
    ) -> SafetyGateVerdict:
        if not is_safety_pipeline_v2_enabled(session, workspace_id):
            with self._metrics.gate_evaluate_duration(intent=intent, cache_hit=False):
                verdict = self._legacy_shim_verdict(
                    session,
                    workspace_id=workspace_id,
                    account_id=account_id,
                    intent=intent,
                )
            self._record_blocked_verdict(workspace_id=workspace_id, verdict=verdict)
            return verdict

        policy = _policy(session, workspace_id=workspace_id)
        terminal_status, safety_grace_period_until = _account_cache_state(
            session, workspace_id=workspace_id, account_id=account_id
        )
        cache_key = _cache_key(
            account_id=account_id,
            intent=intent,
            policy=policy,
            terminal_status=terminal_status,
            safety_grace_period_until=safety_grace_period_until,
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            with self._metrics.gate_evaluate_duration(intent=intent, cache_hit=True):
                verdict = SafetyGateVerdict.model_validate_json(cached)
            self._record_blocked_verdict(workspace_id=workspace_id, verdict=verdict)
            return verdict

        stale_key = _stale_cache_key(account_id=account_id, intent=intent)
        if not self._enforce_cold_call_budget(account_id, intent):
            self._metrics.cold_call_throttled(intent=intent)
            stale = self._cache.get(stale_key)
            if stale is not None:
                with self._metrics.gate_evaluate_duration(intent=intent, cache_hit=True):
                    verdict = SafetyGateVerdict.model_validate_json(stale)
                self._record_blocked_verdict(workspace_id=workspace_id, verdict=verdict)
                return verdict
            verdict = _fail_closed_verdict(account_id=account_id, intent=intent)
            self._record_blocked_verdict(workspace_id=workspace_id, verdict=verdict)
            return verdict

        with self._metrics.gate_evaluate_duration(intent=intent, cache_hit=False):
            verdict = self._compute_verdict(
                session,
                workspace_id=workspace_id,
                account_id=account_id,
                intent=intent,
                policy=policy,
            )
        self._cache.set(cache_key, verdict.model_dump_json(), ttl_seconds=CACHE_TTL_SECONDS)
        if self.redis is not None:
            self._cache.set(
                stale_key,
                verdict.model_dump_json(),
                ttl_seconds=STALE_CACHE_TTL_SECONDS,
            )
        self._record_blocked_verdict(workspace_id=workspace_id, verdict=verdict)
        return verdict

    def _enforce_cold_call_budget(self, account_id: str, intent: str) -> bool:
        """Return True when one cold evaluate call is still allowed this minute."""
        if self.redis is None:
            return True
        key = f"gate:cold:{account_id}:{intent}"
        try:
            count = int(self.redis.incr(key))
            if count == 1:
                self.redis.expire(key, 60)
        except RedisError:
            return True
        return count <= COLD_CALL_BUDGET_PER_MINUTE

    def _record_blocked_verdict(
        self,
        *,
        workspace_id: str,
        verdict: SafetyGateVerdict,
    ) -> None:
        if verdict.severity != "blocked":
            return
        for reason in verdict.reasons:
            if reason.severity == "blocked":
                self._metrics.gate_blocked(
                    workspace_id=workspace_id,
                    intent=verdict.intent,
                    reason=reason.code,
                )

    def _legacy_shim_verdict(
        self,
        session: Session,
        *,
        workspace_id: str,
        account_id: str,
        intent: SafetyGateIntent,
    ) -> SafetyGateVerdict:
        account = _account(session, workspace_id=workspace_id, account_id=account_id)
        reasons: list[SafetyGateReason] = []
        if intent in {"commenting", "warmup"} and not _proxy_healthy(account):
            reasons.append(_proxy_reason("blocked", account))
        if intent == "commenting" and _latest_warmup(session, account=account) is None:
            reasons.append(_reason("no_warmup", "blocked", "Account has no warmup session."))
        quarantine = get_active_quarantine(
            session, account_id=account.id, workspace_id=account.workspace_id
        )
        if quarantine is not None:
            reasons.append(
                _reason(
                    "active_quarantine",
                    "blocked",
                    "Account has an active quarantine.",
                    {"quarantine_id": quarantine.id, "reason": quarantine.reason},
                )
            )
        severity = _aggregate_severity(reasons)
        return SafetyGateVerdict(
            account_id=UUID(account.id),
            intent=intent,
            eligible=severity != "blocked",
            severity=severity,
            reasons=reasons,
            ggr_score=None,
            checked_at=utc_now(),
            cache_ttl_seconds=CACHE_TTL_SECONDS,
        )

    def _compute_verdict(
        self,
        session: Session,
        *,
        workspace_id: str,
        account_id: str,
        intent: SafetyGateIntent,
        policy: WorkspaceSafetyPolicy,
    ) -> SafetyGateVerdict:
        account = _account(session, workspace_id=workspace_id, account_id=account_id)
        effective_mode = _effective_safety_mode(account, policy, utc_now())
        reasons: list[SafetyGateReason] = []
        ggr = get_ggr_score(session, account_id, workspace_id) or calculate_ggr(
            session, account, workspace_id
        )
        ggr_score = float(ggr.score)

        if intent == "commenting":
            reasons.extend(
                _commenting_reasons(session, account=account, policy=policy, ggr_score=ggr_score)
            )
        elif intent == "warmup":
            reasons.extend(_warmup_reasons(account=account, policy=policy))
        elif intent == "editing":
            reasons.extend(_editing_reasons(account=account))
        else:
            raise ValueError(f"unsupported safety gate intent: {intent}")

        if account.terminal_status != "none":
            reasons.append(_terminal_reason(account))

        quarantine = get_active_quarantine(
            session, account_id=account.id, workspace_id=account.workspace_id
        )
        if quarantine is not None:
            reasons.append(
                _reason(
                    "active_quarantine",
                    "blocked",
                    "Account has an active quarantine.",
                    {"quarantine_id": quarantine.id, "reason": quarantine.reason},
                )
            )

        status = _latest_status(session, account=account)
        if status is not None:
            if (
                status.auto_action_taken == "cooldown"
                and _as_utc(status.observed_at) + timedelta(minutes=30) > utc_now()
            ):
                reasons.append(
                    _reason(
                        "ip_change_cooldown",
                        "warning",
                        "Account is in an IP-change cooldown window.",
                        {"observed_at": status.observed_at.isoformat()},
                    )
                )
            consecutive_failure_threshold = get_consecutive_failure_threshold(policy)
            if _is_status_degraded(status, threshold=consecutive_failure_threshold):
                reasons.append(
                    _reason(
                        "status_degraded",
                        "warning",
                        "Recent account status observations are degraded.",
                        {
                            "consecutive_failures": status.consecutive_failures,
                            "consecutive_failure_threshold": consecutive_failure_threshold,
                        },
                    )
                )

        if intent == "commenting":
            load = current_load(session, workspace_id=account.workspace_id, account_id=account.id)
            load_verdict = evaluate_threshold(
                load, _cross_module_safety_mode(policy, effective_mode)
            )
            if load_verdict != "ok":
                self._metrics.cross_module_overload(
                    workspace_id=workspace_id,
                    severity=load_verdict,
                )
                reasons.append(
                    _reason(
                        "cross_module_overload",
                        load_verdict,
                        "Account has too much cross-module activity.",
                        {"last_hour": load.last_hour, "last_24h": load.last_24h},
                    )
                )

        severity = _aggregate_severity(reasons)
        return SafetyGateVerdict(
            account_id=UUID(account.id),
            intent=intent,
            eligible=severity != "blocked",
            severity=severity,
            reasons=reasons,
            ggr_score=ggr_score,
            checked_at=utc_now(),
            cache_ttl_seconds=CACHE_TTL_SECONDS,
        )


def evaluate(
    session: Session,
    *,
    workspace_id: str,
    account_id: str,
    intent: SafetyGateIntent,
    cache: SafetyGateCache | None = None,
) -> SafetyGateVerdict:
    return AccountSafetyGate(cache=cache).evaluate(
        session,
        workspace_id=workspace_id,
        account_id=account_id,
        intent=intent,
    )
