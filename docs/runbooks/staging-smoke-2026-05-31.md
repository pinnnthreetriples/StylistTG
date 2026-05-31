# Staging Smoke Report - 2026-05-31

## Scope

Smoke target: GitHub deployment environment `stylisttg-staging-api`.

Command:

```powershell
cd backend
uv run python -m app.scripts.staging_smoke `
  --base-url <staging-api-url> `
  --include-storage `
  --env-file ../.env.cloud.local `
  --json
```

The run used the safe staging smoke orchestrator. It did not enable live
TDLib/Telegram behavior. Object storage ran in dry-run mode, so no storage
write/read/delete roundtrip was attempted.

## Result

Status: `FAIL`

Passed checks:

- Cloud environment selected `APP_ENV=staging`.
- Supabase JWT auth mode selected.
- Supabase JWKS URL/issuer present; JWKS keys available.
- Runtime and direct Neon database connections succeeded.
- S3-compatible storage config present; storage smoke stayed dry-run.
- Redis temp-key roundtrip passed with the `smoke:stylisttg` key prefix.
- TDLib live mode was disabled and profile execution adapter was `mock`.

Failed checks:

- `/health` returned `503`.
- `/ready` returned `503`.
- Cloud API config is missing `ENFORCE_LOCALHOST_ONLY=false`.
- Cloud API config is missing `OPERATOR_API_TOKEN`.
- Cloud API config is missing explicit non-wildcard `CORS_ORIGINS`.
- Cloud proxy credentials config is missing the required Fernet encryption key.
- `alembic current` returned non-zero during migration-state check.

Skipped / not covered:

- `TEST_SUPABASE_JWT` was not provided, so token verification was skipped.
- Object storage write/read/delete was not run because `--allow-write-cloud` was
  not passed.
- Product workflow smoke flows were not run after readiness failed.

## Follow-Up

Created staging bug #242 for the failed smoke. Architecture-GREEN local
verification is complete, but staging operational evidence is blocked until the
staging API readiness/config/migration-state failures are fixed.
