# Account Risk Foundation

Account Risk is an app-known readiness score. It is not a Telegram anti-ban guarantee and does not perform live TDLib checks.

The module owner is `app.modules.account_safety.risk`.

Compatibility paths remain for existing callers:

- `backend/app/services/account_risk.py`
- `GET /api/accounts/risk-summary`
- `GET /api/accounts/{account_id}/risk`

New behavior should go through the module owner instead of treating the legacy service path as the ownership center.

The dashboard renders backend results through `@stylisttg/api-client`. `apps/dashboard/src/features/accounts/accountRisk.ts` only keeps UI types and threshold helpers compatible with the backend contract.

## Levels

- `low`: 0-24
- `medium`: 25-59
- `high`: 60-79
- `critical`: 80-100

## Factors

The score is deterministic and based only on stored app signals:

- `reauth_required`
- `missing_session`
- `runtime_unhealthy`
- proxy check failures
- active operation cooldowns
- repeated stored job failures
- account locked/unknown state
- profile snapshot not synced

Signals that do not exist yet are left as future factors and are not faked.

## Safety Contract

Risk endpoints are safe for dashboard refresh loops:

- tenant/workspace-scoped like account read/list endpoints;
- read-only;
- no TDLib live calls;
- no Telegram profile/story/music execution;
- no account/session mutation;
- no raw secrets, Redis URLs, DB URLs, S3 keys, JWTs, or TDLib session paths.

## Risk-Gated Actions

`backend/app/services/risk_gate.py` evaluates action gates for future sensitive operations.

- low: allowed;
- medium: allowed with warning;
- high: requires manual override reason;
- critical: blocks unsafe actions, while allowing recovery/lifecycle actions such as reauth, export, and deletion request.

Manual override requires a reason and records a sanitized sensitive audit event. The gate is a backend policy check only; it does not run TDLib or mutate Telegram state.
