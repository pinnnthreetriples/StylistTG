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

- `apps/dashboard/src/lib/http.ts`: low-level legacy request helper kept only for compatibility and old tests.

Auth and auth-batch modules now use `@stylisttg/api-client` wrappers for network calls while keeping their local UI parsing/state helpers. No client code hardcodes Northflank, Render, or staging URLs. Runtime base URL comes from `VITE_API_BASE_URL` or local Vite proxy behavior.

New lifecycle/execution-plane wrappers cover:

- account deletion preview and deletion request;
- account export requests;
- account audit event reads and global audit history;
- account action gate and cooldown reads;
- worker diagnostics, queue taxonomy, and retry policy metadata.

Run `npm run generate:api` after backend route/schema changes and `npm run check:api` before committing.
