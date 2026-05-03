# Audit Log Runbook

## Purpose

Sensitive account lifecycle and execution-plane actions are recorded in `sensitive_audit_event`.

Examples:

- `account.delete.preview`
- `account.delete.requested`
- `account.delete.completed`
- `account.export.requested`
- `account.export.completed`
- `account.risk.override_requested`
- `job.enqueue.blocked_by_risk`
- `job.enqueue.override_used`
- `job.cooldown_applied`
- `session.delete.planned`
- `asset.delete.planned`

## Query

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/audit/events
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/accounts/<account-id>/audit-events
```

Endpoints are tenant/workspace scoped and paginated.

## Sanitization

Audit metadata is sanitized through the secret redaction helpers. These values must never be stored raw:

- passwords, auth codes, tokens, JWTs;
- DB/Redis/S3 URLs;
- S3 access keys and secret keys;
- Supabase service-role keys;
- proxy passwords;
- TDLib auth keys, sessions, and filesystem paths.

IP and user-agent values should be hashed when captured.

## Failure Policy

For destructive/sensitive operations, audit failure should block the operation unless an explicit future policy says otherwise. The current account deletion/export workflow writes audit events before returning success.
