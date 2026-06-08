---
name: deploy
summary: Deployment, staging, cloud, and production runtime memory.
last_updated: 2026-06-08
edges:
  - .mex/context/security.md
  - .mex/context/workers.md
  - .mex/context/setup.md
  - docs/runbooks/cloud-dev-staging-bootstrap.md
  - docs/runbooks/staging-backend-worker-deploy.md
---

# Deploy

## Scope

Use this file for staging, cloud, deploy, branch-protection, smoke, and production-like operations. Local runtime details belong in `.mex/context/setup.md`.

## Non-Negotiables

- Do not deploy, run production smoke, change branch protection, run migrations, or write to cloud storage without explicit operator approval.
- Do not read `.env*`, cloud env files, logs, TDLib sessions, credentials, or runtime artifacts unless the operator approves the exact file/action.
- Live TDLib remains disabled by default in cloud/staging unless a separate runtime/volume/gate plan is reviewed.
- Production-like smoke tooling must stay safe by default: no object writes without `--allow-write-cloud`, no migrations without `--allow-migrations`, and no production smoke without explicit approval.

## Current Staging Shape

- Backend image: `backend/Dockerfile`.
- Web command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Worker command: `python -m rq.cli worker profile_jobs auth_jobs --url $REDIS_URL --worker-class rq.SimpleWorker` or role-aware `app.workers.run_worker` commands when platform resources allow.
- Migration command: `python -m alembic upgrade head`.
- Keep `PROFILE_EXECUTION_ADAPTER=mock` unless a TDLib runtime image/volume plan is approved.

## Cloud Environment Rules

- Neon is the PostgreSQL provider.
- Supabase is auth only; FastAPI remains the only database access layer.
- Backblaze B2, R2, and MinIO-compatible object storage are supported through S3-compatible settings.
- Application assets and TDLib session folders are separate; TDLib session roots must never become public assets or signed URLs.

## Checks

```powershell
cd backend
python -m app.scripts.cloud_config_check
python -m app.scripts.cloud_smoke --safe-default --include-redis --include-storage
python -m app.scripts.staging_smoke --base-url https://<staging-backend> --include-storage --env-file ..\.env.cloud.local
```

## References

- `docs/runbooks/cloud-dev-staging-bootstrap.md`
- `docs/runbooks/staging-backend-worker-deploy.md`
- `docs/quality/REQUIRED_CHECKS.md`
- `render.yaml`
