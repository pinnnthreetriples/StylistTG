# Account Import Runbook

Account import is preview-first. It validates uploaded/imported account packages and never performs automatic mass login.

## Source Types

- `tdlib-directory`: structure validation only.
- `tdata`: archive shape validation only.
- `session-file`: reported as unsupported and requires manual reauth.
- `json-metadata`: schema/metadata preview only.

Unsupported session formats return `unsupported_source_requires_manual_reauth`; the app must not silently attach or convert them.

## API

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/account-import-batches -ContentType 'application/json' -Body '{"source_type":"json-metadata","label":"dry run","dry_run":true}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/account-import-batches/<batch-id>/validate -ContentType 'application/json' -Body '{"dry_run":true}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/account-import-batches/<batch-id>/confirm -ContentType 'application/json' -Body '{"confirmation":"IMPORT"}'
```

## Archive Safety

Validation rejects:

- absolute paths;
- `..` traversal;
- excessive file count;
- excessive uncompressed size;
- excessive depth.

Archives are inspected in safe temporary storage, file contents are not logged, and API responses contain redacted hints only.

## Storage

Import sources are private backend objects under:

```text
imports/<workspace_id>/<batch_id>/source
```

No public signed URL is created by default.
