# Account Lifecycle Security

This slice adds a safe account lifecycle foundation. It does not enable automatic destructive cleanup or live TDLib execution.

## Data Model

- `sensitive_audit_event`: sanitized audit trail for sensitive account, job, export, deletion, override, and lifecycle actions.
- `account_lifecycle_event`: internal lifecycle event stream for account deletion/export workflows.
- `account_deletion_request`: explicit deletion workflow state, preview results, execution results, and failure details.
- `account_export_request`: data portability request state and private storage object metadata.

Audit rows are retained. They must never contain raw credentials, auth codes, proxy passwords, DB/Redis/S3 URLs, JWTs, or TDLib session paths.

## Deletion Flow

1. `GET /api/accounts/{account_id}/deletion-preview` returns planned resource categories and counts.
2. `POST /api/accounts/{account_id}/deletion-requests` requires `confirmation=DELETE` and a reason.
3. The HTTP request records a request and audit event. It does not silently hard-delete the account.
4. `execute_account_deletion_request` is idempotent and lock-ready. Hard delete is blocked unless `ACCOUNT_DELETION_ALLOW_HARD_DELETE=true`.

The preview reports resources such as DB rows, asset object counts, TDLib session presence, jobs, logs, and audit retention policy. It never returns absolute filesystem paths or raw object/session keys.

## Export Flow

`POST /api/accounts/{account_id}/export-requests` creates a private JSON export under:

```text
exports/accounts/<workspace_id>/<account_id>/<request_id>/account-export.json
```

The export excludes TDLib session files and redacts sensitive values. Export metadata is not exposed as a public signed URL by default.

## Retention Policy

- TDLib sessions: delete only through explicit account deletion workflow.
- Uploaded and normalized app assets: planned/deleted through StorageAdapter during approved deletion execution.
- Audit logs: retained redacted.
- Operation/job logs: retained as non-sensitive summaries.
- Export objects: expire according to `ACCOUNT_EXPORT_TTL_DAYS`.
- Deletion requests: retained for lifecycle accountability.

Default config remains safe:

```text
ACCOUNT_DELETION_ALLOW_HARD_DELETE=false
ACCOUNT_DELETION_DRY_RUN_DEFAULT=true
ACCOUNT_EXPORT_TTL_DAYS=7
ACCOUNT_DELETION_LOG_RETENTION_DAYS=90
```

## UI

The Accounts lifecycle modal exposes deletion preview, deletion request creation, export request creation, audit history, cooldowns, and risk gate state. It creates safe dry-run deletion requests by default.
