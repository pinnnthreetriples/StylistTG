# StylistTG

Telegram profile editor MVP: React/TS/Vite + FastAPI + RQ/Redis + TDLib (tdjson.dll).

## Commands

```bash
# Full local launcher on this Windows workstation
.\scripts\start-dev.ps1

# Frontend
npm install          # dependencies
npm run dev          # Vite dev server (proxies /api → localhost:8000)
npm run build        # prod build (tsc + vite)
npm test             # vitest run
npm run lint         # eslint

# Backend
cd backend && pip install -e ".[dev]"
cd backend && python -m uvicorn app.main:app --reload
cd backend && python -m alembic upgrade head
cd backend && python -m pytest -q
cd backend && python -m ruff check .

# Worker (requires running Redis)
cd backend && python -m rq.cli worker profile_jobs --url redis://127.0.0.1:6379/0 --worker-class rq.SimpleWorker
```

## Local Redis

- Prefer portable Memurai at `C:\Tools\Memurai` on this Windows workstation.
- `scripts/start-dev.ps1` starts Memurai on `127.0.0.1:6379` and then starts the RQ worker.
- Do not start Redis through WSL for this project; it has caused localhost/port instability.
- Keep `docker-compose.yml`; it remains the portable Docker option for PostgreSQL + Redis.

## Project Structure

- `src/` — React frontend (App.tsx is the main screen)
- `src/lib/` — API client (`api.ts`), auth logic (`auth.ts`), dashboard logic (`dashboard.ts`)
- `src/components/auth/` — auth UI (phone step, code step, status block)
- `backend/app/api/` — FastAPI routers
- `backend/app/services/` — business logic layer (auth, jobs, dashboard, profile_sync)
- `backend/app/adapters/` — TDLib adapters (auth + profile execution) and mock fallback
- `backend/app/workers/` — RQ worker; `tdlib_job.py` — child subprocess
- `backend/tests/` — pytest tests; shared fakes and helpers live in `conftest.py`
- `docs/` — API spec, runbooks

## Architecture Rules

- `account_profile_state` is the source of truth for current profile (not job payloads)
- Parent worker writes final truth to DB; child subprocess does not
- Frontend is polling-first; no WebSocket/SSE
- PostgreSQL is the dedup source of truth, not Redis
- Queue execution depends on external Redis + RQ worker processes

## Agent Startup

- At the start of a new session, activate the current project with Serena and check onboarding.
- Read `AGENT_HANDOFF.md` immediately; it is the current project memory for future sessions.
- Use Superpowers as the primary process skill set when the task fits its workflows.
- Always follow `karpathy-guidelines`: clarify assumptions first, then make minimal surgical changes with verification.
- Use Spec Kit as the default planning path; use Superpowers brainstorming before it when the task is unclear, product-heavy, UI/UX-heavy, or has meaningful tradeoffs.
- Do not modify application source code before the planning path is chosen and agreed, unless the task is a small obvious fix.

## Code Standards

- Python 3.12+, ruff for linting, type hints everywhere
- TypeScript strict, functional React + hooks, Tailwind CSS v4
- `@stylisttg/ui` is the single product UI system for dashboard modules. Do not import `apps/dashboard/src/components/ui/*` directly in product modules when an equivalent exists in `@stylisttg/ui`; shadcn-style files are references/scaffolding, not a parallel design system.

## Testing

- Backend: pytest with `integration` and `live` markers; shared fakes in `conftest.py`
- Frontend: vitest; pure unit tests for logic in `src/lib/`
- Run single test: `python -m pytest tests/test_auth_service.py::test_name -q`

## Safety & Permissions

**OK without asking:** read files, run lint/tsc/tests, local code changes, UI work

**Ask first:** live TDLib calls against real Telegram, `pip install`/`npm install`, git push, file deletion

**Never:** commit `.env` or API keys, modify files outside current task scope

## Reference Docs

- Architecture handoff → `AGENT_HANDOFF.md`
- Frontend API spec → `docs/api/frontend.md`
- Live validation → `docs/runbooks/live-validation.md`

<!-- SPECKIT START -->
Current Spec Kit plan: `specs/001-account-preparation/plan.md`
<!-- SPECKIT END -->
