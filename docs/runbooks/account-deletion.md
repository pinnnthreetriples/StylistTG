# Account Deletion Runbook

## Goal

Delete account-owned application data through an explicit, auditable workflow. Do not use direct database deletes or filesystem deletes.

## Preview

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/api/accounts/<account-id>/deletion-preview
```

The preview shows planned resource categories and counts. It must not expose raw TDLib session paths, object keys that contain sensitive details, or local filesystem paths.

## Request

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/accounts/<account-id>/deletion-requests `
  -ContentType 'application/json' `
  -Body '{"reason":"operator requested account deletion","confirmation":"DELETE","dry_run":true}'
```

Rules:

- reason is required;
- confirmation must be `DELETE`;
- requests are tenant/workspace scoped;
- audit event is recorded;
- default flow is dry-run/safe foundation.

## Execution

`execute_account_deletion_request` is the executor foundation. By default it does not hard-delete because:

```text
ACCOUNT_DELETION_ALLOW_HARD_DELETE=false
```

Only a future reviewed operational flow should enable hard deletion. It must preserve audit logs and use StorageAdapter for object deletion.

## Retention

- audit events: retained redacted;
- deletion requests: retained;
- export requests: retained with private object TTL metadata;
- TDLib sessions: deleted only through approved account deletion workflow;
- assets: deleted or marked through StorageAdapter;
- operation/job logs: retained as non-sensitive summaries.

## Rollback

For a dry-run/request-only failure, cancel or leave the request as failed. Do not manually delete DB rows, Redis keys, object storage keys, or TDLib sessions.
