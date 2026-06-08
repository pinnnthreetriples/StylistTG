# Frontend SaaS Foundation

> Status: historical architecture snapshot from the SaaS foundation PR.
> Current frontend source of truth starts at `.mex/context/frontend.md` and `docs/api/frontend.md`.

This PR added a SaaS dashboard foundation without changing backend deployment or live Telegram execution.

## Product Zones

The dashboard shell is structured for:

- Accounts
- Health Center
- Jobs
- Warmup
- Proxy Center
- Settings
- Billing

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

CI also runs:

```powershell
npm run check:api
```

That command fails when generated OpenAPI artifacts are stale. The dashboard now routes active calls through `@stylisttg/api-client`; `apps/dashboard/src/lib/api.ts` remains as a compatibility wrapper for existing imports.

## Health and Risk

Health Center shows API liveness, readiness, database, Redis, TDLib mode, app environment, auth mode, storage posture, and aggregate account risk from backend-backed endpoints:

- `GET /diagnostics/frontend-summary`
- `GET /api/accounts/risk-summary`

Account Risk is a deterministic backend app-known readiness score based on stored account state, runtime health, proxy/cooldown/job-failure signals, and profile sync posture. It is not a Telegram anti-ban guarantee and does not run live TDLib checks.

## Browser QA

```powershell
npm run qa:browser
npm run qa:screenshots
```

Playwright builds the dashboard, starts Vite preview, mocks backend API responses, checks SaaS shell pages, and writes screenshots as ignored artifacts.

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
