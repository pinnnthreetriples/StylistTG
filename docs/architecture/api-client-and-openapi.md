# API Client and OpenAPI Drift

The dashboard API layer is now centered on `@stylisttg/api-client`.

## Generation

```powershell
npm run generate:api
```

This exports the FastAPI schema with `backend/app/scripts/export_openapi.py`, updates `packages/api-client/openapi.json`, and regenerates `packages/api-client/src/generated/schema.d.ts` with `openapi-typescript`.

## Drift Check

```powershell
npm run check:api
```

The check writes OpenAPI and TypeScript outputs into a temporary directory, compares them with committed artifacts, and fails with instructions when either artifact is stale. CI runs this before frontend lint/test/build.

Checked files:

- `packages/api-client/openapi.json`
- `packages/api-client/src/generated/schema.d.ts`

## Dashboard Migration

`apps/dashboard/src/lib/api.ts` is now a compatibility wrapper over `@stylisttg/api-client`. Active dashboard calls should be added to `packages/api-client/src/client.ts` first, then exposed through the wrapper only when existing dashboard imports still need the legacy path.

Remaining manual dashboard API helpers outside that wrapper:

- `apps/dashboard/src/lib/http.ts`: low-level legacy request helper kept for auth/auth-batch modules.
- `apps/dashboard/src/lib/auth.ts`: auth flow endpoints remain isolated because they have custom UI/session behavior.
- `apps/dashboard/src/lib/authBatches.ts`: batch-auth flow remains a future endpoint-by-endpoint migration.

No client code hardcodes Northflank, Render, or staging URLs. Runtime base URL comes from `VITE_API_BASE_URL` or local Vite proxy behavior.
