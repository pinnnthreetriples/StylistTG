# Staging Smoke Test

Post-deploy smoke checks for staging environment.

## Prerequisites

- Staging deployment is complete and healthy
- You have admin credentials (Supabase JWT or operator token)
- Runtime env matches `docs/runbooks/northflank-staging-readiness.md`, including
  cloud API guard vars, proxy credential encryption key, and direct migration URL
- `curl` or HTTP client available

## Smoke Steps

### 1. Health & Readiness

```bash
# Public health endpoint
curl -f https://<staging>/health
# Expected: 200

# Public readiness — must NOT expose database/redis/tdlib internals
curl -s https://<staging>/ready | jq .
# Expected: { "status": "ok" } — no connection strings, no internal details
```

For endpoint-only triage without reading local cloud env files:

```powershell
cd backend
python -m app.scripts.staging_smoke --base-url https://<staging> --endpoint-only --json
```

### 2. Authentication

```bash
# Authenticated user info
curl -H "Authorization: Bearer <token>" https://<staging>/api/me
# Expected: 200 with user_id, workspace_id, role
```

### 3. Accounts

```bash
# List accounts (requires auth)
curl -H "Authorization: Bearer <token>" https://<staging>/api/accounts
# Expected: 200 with array
```

### 4. Diagnostics — Role Enforcement

```bash
# Admin access to runtime diagnostics
curl -H "Authorization: Bearer <admin-token>" https://<staging>/diagnostics/runtime
# Expected: 200

# Non-admin (operator/viewer) should be rejected
curl -H "Authorization: Bearer <viewer-token>" https://<staging>/diagnostics/runtime
# Expected: 403
```

### 5. Account Creation

Create a test account via the dashboard or API to verify the full account creation flow works.

### 6. Asset Upload

```bash
# Upload a small test image
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@test-image.jpg" \
  https://<staging>/api/assets/profile-photo
# Expected: 200 with asset id
```

### 7. Job Preview

```bash
# Preview a profile update (dry-run, no Telegram calls)
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"account_id": "<account-id>", "name": "Test"}' \
  https://<staging>/api/jobs/profile/preview
# Expected: 200 with preview payload
```

### 8. Worker Diagnostics (Admin)

```bash
curl -H "Authorization: Bearer <admin-token>" https://<staging>/api/workers/diagnostics
# Expected: 200 with queue status
```

### 9. Security Spot Checks

- Verify `/ready` does not expose database URLs, Redis URLs, or TDLib paths
- Verify unauthenticated requests to `/api/accounts` return 401
- Verify viewer role cannot POST/PATCH/DELETE
- Verify cross-workspace account IDs return 404
