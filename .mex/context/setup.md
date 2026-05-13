---
name: setup
description: Local setup, ports, Redis, and common commands.
triggers:
  - setup
  - install
  - run
  - port
edges:
  - .mex/context/stack.md
  - .mex/context/workers.md
  - README.md
last_updated: 2026-05-13
---

# Setup

## Local launcher

```powershell
.\scripts\start-dev.ps1
```

On this Windows workstation the launcher starts Memurai Redis at `127.0.0.1:6379`, applies migrations, starts FastAPI on localhost port `8002`, starts profile/auth RQ workers, and starts Vite on localhost port `5173`.

## Manual backend

```powershell
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8002
```

## Manual frontend

```powershell
npm install
npm run dashboard:dev
```

## Manual workers

```powershell
cd backend; python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
cd backend; python -m rq.cli worker auth_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
```

Warmup workers are manual and only needed for warmup testing.

## Port rule

- Dashboard local dev expects backend `8002`.
- `.env.example` uses `VITE_API_BASE_URL=http://localhost:8002` for dashboard dev.
- `scripts/start_backend.ps1` and live-validation helper scripts default to `8000`.
- Do not blindly replace every `8000` reference; check whether it is live-validation specific.
- Cloudflare Pages production deploy should track `main` only; PR/preview deployments are disabled in Cloudflare project settings or restricted through branch controls.
