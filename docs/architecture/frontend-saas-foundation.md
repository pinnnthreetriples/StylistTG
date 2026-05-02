# Frontend SaaS Foundation

This PR adds a SaaS dashboard foundation without changing backend deployment or live Telegram execution.

## Product Zones

The dashboard shell is structured for:

- Accounts
- Health Center
- Jobs
- Proxy Center
- Settings
- future Billing

The existing account list, workspace editor, auth batch flow, operations journal, and settings behavior remain in place. New foundation components are read-only or preview-only.

## TanStack Foundations

- `AccountsTable` uses TanStack Table for sorting, filtering, row selection, and column visibility state.
- `BatchImportForm` uses TanStack Form for a dry-run-only account import preview. It does not call import endpoints.
- `VirtualJobLogList` uses TanStack Virtual for large read-only job/log lists.

## API Client

OpenAPI types are generated from FastAPI:

```powershell
npm run generate:api
```

This runs `backend/app/scripts/export_openapi.py`, writes `packages/api-client/openapi.json`, and generates `packages/api-client/src/generated/schema.d.ts`.

The dashboard now uses `@stylisttg/api-client` for account list, latest jobs, and runtime diagnostics. The remaining manual API types stay in `apps/dashboard/src/lib/api.ts` and can be migrated endpoint-by-endpoint.

## Staging Contour

Current staging remains:

- Northflank API
- Northflank Worker
- Neon Postgres
- Upstash Redis
- Backblaze B2/S3-compatible object storage
- Supabase JWKS
- `PROFILE_EXECUTION_ADAPTER=mock`, TDLib live runtime disabled/not configured

This foundation does not run live Telegram/TDLib actions, real account import, profile/story/music jobs, cleanup, or production deploys.
